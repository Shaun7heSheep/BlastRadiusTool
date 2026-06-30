using BlastRadiusUI.Models;

namespace BlastRadiusUI.Tests;

public class AppFilterTests
{
    private static GraphData CreateTestGraph() => new(
        new List<ApplicationInfo>
        {
            new("INT-INV-01", "Inventory Management"),
            new("INT-NTF-01", "Notifications"),
            new("INT-ORD-01", "Order Processing"),
            new("INT-PAY-01", "Payments Processing"),
            new("SHARED", "Shared Infrastructure"),
        },
        new List<ServiceNode>
        {
            new("payments-servicebus", "Payments Service Bus", "service-bus", new List<string> { "INT-PAY-01" }, "high"),
            new("order-function", "Order Function", "function-app", new List<string> { "INT-ORD-01" }, "high"),
            new("inventory-function", "Inventory Function", "function-app", new List<string> { "INT-INV-01" }, "high"),
            new("notification-function", "Notification Function", "function-app", new List<string> { "INT-NTF-01" }, "medium"),
            new("cosmos-db", "Cosmos DB", "cosmos-db", new List<string> { "SHARED" }, "high"),
            new("order-db", "Order Database", "sql-database", new List<string> { "INT-ORD-01" }, "high"),
            new("api-management", "API Management", "api-management", new List<string> { "SHARED" }, "high"),
            new("app-insights", "Application Insights", "application-insights", new List<string> { "SHARED" }, "medium"),
            new("key-vault", "Key Vault", "key-vault", new List<string> { "SHARED" }, "high"),
            new("blob-storage", "Blob Storage", "storage-account", new List<string> { "SHARED" }, "medium"),
        },
        new List<DependencyEdge>()
    );

    [Fact]
    public void ExtractAppNames_ReturnsDistinctSorted()
    {
        var graph = CreateTestGraph();
        var appIds = graph.Applications
            .OrderBy(a => a.Id)
            .Select(a => a.Id)
            .ToList();

        Assert.Equal(5, appIds.Count);
        Assert.Equal(new[] { "INT-INV-01", "INT-NTF-01", "INT-ORD-01", "INT-PAY-01", "SHARED" }, appIds);
    }

    [Fact]
    public void ExtractAppNames_EmptyGraph_ReturnsEmptyList()
    {
        var graph = new GraphData(new List<ApplicationInfo>(), new List<ServiceNode>(), new List<DependencyEdge>());
        var appIds = graph.Applications
            .OrderBy(a => a.Id)
            .Select(a => a.Id)
            .ToList();

        Assert.Empty(appIds);
    }

    [Fact]
    public void FilterNodesByApp_Orders_ReturnsCorrectIds()
    {
        var graph = CreateTestGraph();
        var nodeIds = graph.Nodes
            .Where(n => n.AppIds.Contains("INT-ORD-01"))
            .Select(n => n.Id)
            .ToList();

        Assert.Equal(2, nodeIds.Count);
        Assert.Contains("order-function", nodeIds);
        Assert.Contains("order-db", nodeIds);
    }

    [Fact]
    public void FilterNodesByApp_Shared_ReturnsAllSharedServices()
    {
        var graph = CreateTestGraph();
        var nodeIds = graph.Nodes
            .Where(n => n.AppIds.Contains("SHARED"))
            .Select(n => n.Id)
            .ToList();

        Assert.Equal(5, nodeIds.Count);
        Assert.Contains("cosmos-db", nodeIds);
        Assert.Contains("api-management", nodeIds);
        Assert.Contains("app-insights", nodeIds);
        Assert.Contains("key-vault", nodeIds);
        Assert.Contains("blob-storage", nodeIds);
    }

    [Fact]
    public void FilterNodesByApp_UnknownApp_ReturnsEmpty()
    {
        var graph = CreateTestGraph();
        var nodeIds = graph.Nodes
            .Where(n => n.AppIds.Contains("NONEXISTENT"))
            .Select(n => n.Id)
            .ToList();

        Assert.Empty(nodeIds);
    }
}
