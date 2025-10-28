import { useEffect, useState } from "react";
import { apiClient } from "app";
import type { InstalledPackagesResponse, InstalledPackage } from "types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Package, Search } from "lucide-react";
import { useWorkspaceStore } from "utils/workspaceStore";

export default function InstalledPackagesPage() {
  const [data, setData] = useState<InstalledPackagesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("all");
  const { projectId } = useWorkspaceStore();

  useEffect(() => {
    if (projectId) {
      loadPackages();
    }
  }, [projectId]);

  const loadPackages = async () => {
    if (!projectId) {
      console.error("No project ID available");
      return;
    }
    
    try {
      setLoading(true);
      const response = await apiClient.get_installed_packages({ projectId });
      const result = await response.json();
      setData(result);
    } catch (error) {
      console.error("Failed to load packages:", error);
    } finally {
      setLoading(false);
    }
  };

  const filterPackages = (packages: InstalledPackage[]) => {
    if (!searchQuery) return packages;
    return packages.filter((pkg) =>
      pkg.name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  };

  const renderPackageTable = (packages: InstalledPackage[], type: string) => {
    const filtered = filterPackages(packages);

    if (filtered.length === 0) {
      return (
        <div className="text-center py-12 text-muted-foreground">
          {searchQuery ? (
            <p>No packages found matching "{searchQuery}"</p>
          ) : (
            <p>No {type} packages installed</p>
          )}
        </div>
      );
    }

    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Package Name</TableHead>
            <TableHead>Version</TableHead>
            <TableHead>Type</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((pkg) => (
            <TableRow key={`${pkg.package_manager}-${pkg.name}`}>
              <TableCell className="font-mono font-medium">{pkg.name}</TableCell>
              <TableCell className="font-mono text-muted-foreground">
                v{pkg.version}
              </TableCell>
              <TableCell>
                <Badge
                  variant={pkg.package_manager === "pip" ? "default" : "secondary"}
                >
                  {pkg.package_manager}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-7xl mx-auto">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-muted rounded w-1/4"></div>
            <div className="h-64 bg-muted rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-7xl mx-auto text-center">
          <p className="text-destructive">Failed to load packages</p>
        </div>
      </div>
    );
  }

  const allPackages = [...data.python_packages, ...data.npm_packages];
  const filteredAll = filterPackages(allPackages);

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <Package className="h-8 w-8" />
              Installed Packages
            </h1>
            <p className="text-muted-foreground mt-2">
              View all installed dependencies in your project
            </p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold">{data.total_count}</div>
            <div className="text-sm text-muted-foreground">Total Packages</div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Python Packages</CardTitle>
              <CardDescription>Installed via pip (uv)</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-4xl font-bold">{data.python_packages.length}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">NPM Packages</CardTitle>
              <CardDescription>Installed via yarn</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-4xl font-bold">{data.npm_packages.length}</div>
            </CardContent>
          </Card>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search packages..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Packages Table */}
        <Card>
          <CardContent className="pt-6">
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="all">
                  All ({filteredAll.length})
                </TabsTrigger>
                <TabsTrigger value="python">
                  Python ({filterPackages(data.python_packages).length})
                </TabsTrigger>
                <TabsTrigger value="npm">
                  NPM ({filterPackages(data.npm_packages).length})
                </TabsTrigger>
              </TabsList>

              <TabsContent value="all" className="mt-6">
                {renderPackageTable(allPackages, "all")}
              </TabsContent>

              <TabsContent value="python" className="mt-6">
                {renderPackageTable(data.python_packages, "Python")}
              </TabsContent>

              <TabsContent value="npm" className="mt-6">
                {renderPackageTable(data.npm_packages, "NPM")}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
