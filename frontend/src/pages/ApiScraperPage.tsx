import { useState } from "react";
import { apiClient } from "app";
import type { ScrapeResponse, ApiEndpoint } from "types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Search, Code, Globe } from "lucide-react";

export default function ApiScraperPage() {
  const [url, setUrl] = useState("https://docs.github.com/en/rest");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScrapeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleScrape = async () => {
    if (!url) {
      setError("Please enter a URL");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setResult(null);

      const response = await apiClient.scrape_api_docs({
        url: url,
      });

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Failed to scrape documentation");
      console.error("Scrape error:", err);
    } finally {
      setLoading(false);
    }
  };

  const getMethodColor = (method: string) => {
    switch (method.toUpperCase()) {
      case "GET":
        return "default";
      case "POST":
        return "secondary";
      case "PUT":
        return "outline";
      case "DELETE":
        return "destructive";
      default:
        return "outline";
    }
  };

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Code className="h-8 w-8" />
            API Documentation Scraper
          </h1>
          <p className="text-muted-foreground mt-2">
            Extract API endpoints from documentation pages using Scrapy
          </p>
        </div>

        {/* Input Section */}
        <Card>
          <CardHeader>
            <CardTitle>Enter Documentation URL</CardTitle>
            <CardDescription>
              Paste the URL of an API documentation page to extract endpoints
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <div className="flex-1 relative">
                <Globe className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="https://docs.github.com/en/rest"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  className="pl-10"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleScrape();
                    }
                  }}
                />
              </div>
              <Button
                onClick={handleScrape}
                disabled={loading || !url}
                className="min-w-[120px]"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Scraping...
                  </>
                ) : (
                  <>
                    <Search className="h-4 w-4 mr-2" />
                    Scrape
                  </>
                )}
              </Button>
            </div>

            {error && (
              <Alert variant="destructive" className="mt-4">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* Results */}
        {result && (
          <div className="space-y-4">
            {/* Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Total Endpoints
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold">{result.total_count}</div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Page Title
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-lg font-medium truncate">
                    {result.page_title || "N/A"}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Source URL
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <a
                    href={result.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-500 hover:underline truncate block"
                  >
                    {result.url}
                  </a>
                </CardContent>
              </Card>
            </div>

            {/* Endpoints Table */}
            <Card>
              <CardHeader>
                <CardTitle>Discovered Endpoints</CardTitle>
                <CardDescription>
                  API endpoints extracted from the documentation
                </CardDescription>
              </CardHeader>
              <CardContent>
                {result.endpoints.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <p>No endpoints found on this page</p>
                    <p className="text-sm mt-2">
                      Try a different documentation URL
                    </p>
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Method</TableHead>
                        <TableHead>Path</TableHead>
                        <TableHead>Description</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.endpoints.map((endpoint, idx) => (
                        <TableRow key={idx}>
                          <TableCell>
                            <Badge variant={getMethodColor(endpoint.method)}>
                              {endpoint.method}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-sm">
                            {endpoint.path}
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {endpoint.description || "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
