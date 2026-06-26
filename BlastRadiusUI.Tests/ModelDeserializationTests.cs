using System.Text.Json;
using BlastRadiusUI.Models;

namespace BlastRadiusUI.Tests;

public class ModelDeserializationTests
{
    private static readonly JsonSerializerOptions SnakeCaseOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
    };

    [Fact]
    public void Deserialize_BlastRadiusResult_FromSnakeCaseJson()
    {
        var json = """
        {
            "failed_node": "payments-servicebus",
            "affected_nodes": ["order-function", "api-management"],
            "affected_edges": [{"source": "order-function", "target": "payments-servicebus"}],
            "timestamp": "2026-06-26T10:00:00Z"
        }
        """;
        var result = JsonSerializer.Deserialize<BlastRadiusResult>(json, SnakeCaseOptions);
        Assert.NotNull(result);
        Assert.Equal("payments-servicebus", result.FailedNode);
        Assert.Equal(2, result.AffectedNodes.Count);
        Assert.Contains("order-function", result.AffectedNodes);
        Assert.Single(result.AffectedEdges);
    }

    [Fact]
    public void Deserialize_GraphData_FromSnakeCaseJson()
    {
        var json = """
        {
            "nodes": [
                {"id": "payments-servicebus", "label": "Payments Service Bus", "azure_type": "service-bus", "app": "payments", "criticality": "high"}
            ],
            "edges": [
                {"source": "order-function", "target": "payments-servicebus"}
            ]
        }
        """;
        var result = JsonSerializer.Deserialize<GraphData>(json, SnakeCaseOptions);
        Assert.NotNull(result);
        Assert.Single(result.Nodes);
        Assert.Equal("payments-servicebus", result.Nodes[0].Id);
        Assert.Equal("service-bus", result.Nodes[0].AzureType);
        Assert.Single(result.Edges);
    }

    [Fact]
    public void Deserialize_ServiceNode_AllProperties()
    {
        var json = """{"id": "cosmos-db", "label": "Cosmos DB", "azure_type": "cosmos-db", "app": "shared", "criticality": "high"}""";
        var node = JsonSerializer.Deserialize<ServiceNode>(json, SnakeCaseOptions);
        Assert.NotNull(node);
        Assert.Equal("cosmos-db", node.Id);
        Assert.Equal("Cosmos DB", node.Label);
        Assert.Equal("cosmos-db", node.AzureType);
        Assert.Equal("shared", node.App);
        Assert.Equal("high", node.Criticality);
    }

    [Fact]
    public void Deserialize_DependencyEdge()
    {
        var json = """{"source": "order-function", "target": "payments-servicebus"}""";
        var edge = JsonSerializer.Deserialize<DependencyEdge>(json, SnakeCaseOptions);
        Assert.NotNull(edge);
        Assert.Equal("order-function", edge.Source);
        Assert.Equal("payments-servicebus", edge.Target);
    }

    [Fact]
    public void Deserialize_SignalRNegotiateResponse()
    {
        var json = """{"url": "https://myservice.service.signalr.net/client", "access_token": "eyJhbGciOiJIUz..."}""";
        var response = JsonSerializer.Deserialize<SignalRNegotiateResponse>(json, SnakeCaseOptions);
        Assert.NotNull(response);
        Assert.Equal("https://myservice.service.signalr.net/client", response.Url);
        Assert.Equal("eyJhbGciOiJIUz...", response.AccessToken);
    }

    [Fact]
    public void Deserialize_BlastRadiusResult_EmptyAffectedNodes()
    {
        var json = """
        {
            "failed_node": "api-management",
            "affected_nodes": [],
            "affected_edges": [],
            "timestamp": "2026-06-26T10:00:00Z"
        }
        """;
        var result = JsonSerializer.Deserialize<BlastRadiusResult>(json, SnakeCaseOptions);
        Assert.NotNull(result);
        Assert.Empty(result.AffectedNodes);
        Assert.Empty(result.AffectedEdges);
    }
}
