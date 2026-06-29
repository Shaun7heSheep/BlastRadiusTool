using BlastRadiusUI.Models;

namespace BlastRadiusUI.Tests;

public class AppFilterTests
{
    private static GraphData CreateTestGraph() => new(
        new List<ServiceNode>
        {
            new("payments-servicebus", "Payments Service Bus", "service-bus", "payments", "high"),
            new("order-function", "Order Function", "function-app", "orders", "high"),
            new("inventory-function", "Inventory Function", "function-app", "inventory", "high"),
            new("notification-function", "Notification Function", "function-app", "notifications", "medium"),
            new("cosmos-db", "Cosmos DB", "cosmos-db", "shared", "high"),
            new("order-db", "Order Database", "sql-database", "orders", "high"),
            new("api-management", "API Management", "api-management", "shared", "high"),
            new("app-insights", "Application Insights", "application-insights", "shared", "medium"),
            new("key-vault", "Key Vault", "key-vault", "shared", "high"),
            new("blob-storage", "Blob Storage", "storage-account", "shared", "medium"),
        },
        new List<DependencyEdge>()
    );

    [Fact]
    public void ExtractAppNames_ReturnsDistinctSorted()
    {
        var graph = CreateTestGraph();
        var appNames = graph.Nodes
            .Select(n => n.App)
            .Distinct()
            .OrderBy(a => a)
            .ToList();

        Assert.Equal(5, appNames.Count);
        Assert.Equal(new[] { "inventory", "notifications", "orders", "payments", "shared" }, appNames);
    }

    [Fact]
    public void ExtractAppNames_EmptyGraph_ReturnsEmptyList()
    {
        var graph = new GraphData(new List<ServiceNode>(), new List<DependencyEdge>());
        var appNames = graph.Nodes
            .Select(n => n.App)
            .Distinct()
            .OrderBy(a => a)
            .ToList();

        Assert.Empty(appNames);
    }

    [Fact]
    public void FilterNodesByApp_Orders_ReturnsCorrectIds()
    {
        var graph = CreateTestGraph();
        var nodeIds = graph.Nodes
            .Where(n => n.App == "orders")
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
            .Where(n => n.App == "shared")
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
            .Where(n => n.App == "nonexistent")
            .Select(n => n.Id)
            .ToList();

        Assert.Empty(nodeIds);
    }
}
