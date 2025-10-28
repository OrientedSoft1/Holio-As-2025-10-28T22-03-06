from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.http import Response
import json
import multiprocessing
from queue import Queue
import threading

router = APIRouter()

class ApiEndpoint(BaseModel):
    """Model for a scraped API endpoint"""
    method: str  # GET, POST, PUT, DELETE, etc.
    path: str
    description: Optional[str] = None
    parameters: List[str] = []

class ScrapeRequest(BaseModel):
    """Request to scrape API documentation"""
    url: HttpUrl
    
class ScrapeResponse(BaseModel):
    """Response with scraped API endpoints"""
    url: str
    endpoints: List[ApiEndpoint]
    total_count: int
    page_title: Optional[str] = None

class ApiDocSpider(scrapy.Spider):
    """Spider for scraping API documentation pages"""
    name = 'api_doc_spider'
    
    def __init__(self, start_url: str, result_queue: Queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = [start_url]
        self.result_queue = result_queue
        self.endpoints = []
        self.page_title = None
    
    def parse(self, response: Response):
        """Parse the API documentation page"""
        # Extract page title
        self.page_title = response.css('title::text').get() or response.css('h1::text').get()
        
        # Look for common API documentation patterns
        # This is a simple heuristic - can be improved based on specific doc site structure
        
        # Pattern 1: Look for code blocks with HTTP methods
        http_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
        
        # Find code blocks and pre tags
        code_blocks = response.css('code::text, pre::text').getall()
        
        for block in code_blocks:
            for method in http_methods:
                if method in block:
                    # Try to extract the path
                    lines = block.split('\n')
                    for line in lines:
                        if method in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                # Likely format: "GET /api/endpoint"
                                path = parts[1] if parts[1].startswith('/') else '/' + parts[1]
                                
                                self.endpoints.append({
                                    'method': method,
                                    'path': path,
                                    'description': None,
                                    'parameters': []
                                })
        
        # Pattern 2: Look for endpoint paths in links
        api_links = response.css('a[href*="/api/"]::attr(href)').getall()
        for link in api_links[:10]:  # Limit to first 10
            self.endpoints.append({
                'method': 'GET',
                'path': link,
                'description': None,
                'parameters': []
            })
        
        # Pattern 3: Look for tables with endpoint information
        tables = response.css('table')
        for table in tables:
            rows = table.css('tr')
            for row in rows:
                cells = row.css('td::text').getall()
                if len(cells) >= 2:
                    # Check if first cell contains HTTP method
                    if any(method in cells[0].upper() for method in http_methods):
                        method = cells[0].strip().upper()
                        path = cells[1].strip()
                        description = cells[2].strip() if len(cells) > 2 else None
                        
                        self.endpoints.append({
                            'method': method,
                            'path': path,
                            'description': description,
                            'parameters': []
                        })
        
        # Remove duplicates based on method + path
        seen = set()
        unique_endpoints = []
        for ep in self.endpoints:
            key = f"{ep['method']}:{ep['path']}"
            if key not in seen:
                seen.add(key)
                unique_endpoints.append(ep)
        
        self.endpoints = unique_endpoints
    
    def closed(self, reason):
        """Called when spider closes - put results in queue"""
        self.result_queue.put({
            'endpoints': self.endpoints,
            'page_title': self.page_title
        })

def run_spider(url: str, result_queue: Queue):
    """Run spider in a separate process"""
    process = CrawlerProcess(settings={
        'USER_AGENT': 'Mozilla/5.0 (compatible; RiffAPIScraperBot/1.0)',
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 1,
        'LOG_LEVEL': 'ERROR'
    })
    
    process.crawl(ApiDocSpider, start_url=url, result_queue=result_queue)
    process.start()

@router.post("/scrape-api-docs")
async def scrape_api_docs(request: ScrapeRequest) -> ScrapeResponse:
    """
    Scrape API documentation from a given URL
    
    This uses Scrapy to extract API endpoints, methods, and descriptions
    from API documentation pages.
    """
    
    url = str(request.url)
    
    print(f"Starting scrape of API docs from: {url}")
    
    # Create a queue for results
    result_queue = multiprocessing.Queue()
    
    # Run spider in separate process (Scrapy requirement)
    spider_process = multiprocessing.Process(
        target=run_spider,
        args=(url, result_queue)
    )
    
    spider_process.start()
    spider_process.join(timeout=30)  # 30 second timeout
    
    if spider_process.is_alive():
        spider_process.terminate()
        spider_process.join()
        raise HTTPException(
            status_code=408,
            detail="Scraping took too long (>30s)"
        )
    
    # Get results from queue
    if result_queue.empty():
        raise HTTPException(
            status_code=500,
            detail="Failed to scrape documentation"
        )
    
    result = result_queue.get()
    
    endpoints = [
        ApiEndpoint(**ep) for ep in result.get('endpoints', [])
    ]
    
    print(f"Scraped {len(endpoints)} endpoints from {url}")
    
    return ScrapeResponse(
        url=url,
        endpoints=endpoints,
        total_count=len(endpoints),
        page_title=result.get('page_title')
    )
