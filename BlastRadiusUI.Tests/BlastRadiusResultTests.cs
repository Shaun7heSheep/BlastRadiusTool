using BlastRadiusUI.Models;

namespace BlastRadiusUI.Tests;

public class BlastRadiusResultTests
{
    [Fact]
    public void Constructor_SetsAllProperties()
    {
        var edges = new List<DependencyEdge> { new("order-function", "payments-servicebus") };
        var result = new BlastRadiusResult(
            "payments-servicebus",
            new List<string> { "order-function", "api-management" },
            edges,
            DateTimeOffset.Parse("2026-06-26T10:00:00Z")
        );

        Assert.Equal("payments-servicebus", result.FailedNode);
        Assert.Equal(2, result.AffectedNodes.Count);
        Assert.Single(result.AffectedEdges);
    }

    [Fact]
    public void AffectedNodes_IsList()
    {
        var result = new BlastRadiusResult(
            "test-node",
            new List<string> { "a", "b" },
            new List<DependencyEdge>(),
            DateTimeOffset.UtcNow
        );
        Assert.IsType<List<string>>(result.AffectedNodes);
    }

    [Fact]
    public void GraphData_Constructor()
    {
        var nodes = new List<ServiceNode> { new("id", "label", "type", new List<string> { "APP-01" }, "high") };
        var edges = new List<DependencyEdge> { new("a", "b") };
        var graph = new GraphData(new List<ApplicationInfo>(), nodes, edges);
        Assert.Single(graph.Nodes);
        Assert.Single(graph.Edges);
    }

    [Fact]
    public void ServiceNode_RecordEquality()
    {
        // Share the same List instance — List<T> uses reference equality
        // in record comparisons, so two separate lists would not be equal.
        var appIds = new List<string> { "APP-01" };
        var a = new ServiceNode("id", "label", "type", appIds, "high");
        var b = new ServiceNode("id", "label", "type", appIds, "high");
        Assert.Equal(a, b);
    }

    [Fact]
    public void DependencyEdge_RecordEquality()
    {
        var a = new DependencyEdge("src", "tgt");
        var b = new DependencyEdge("src", "tgt");
        Assert.Equal(a, b);
    }
}
