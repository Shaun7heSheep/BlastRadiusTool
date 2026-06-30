using System.Text.Json;
using BlastRadiusUI.Models;

namespace BlastRadiusUI.Tests;

public class ModelDeserializationTests
{
    private static readonly JsonSerializerOptions WebOptions = new(JsonSerializerDefaults.Web);

    [Fact]
    public void Deserialize_BlastRadiusResult_FromCamelCaseJson()
    {
        var json = """
        {
            "failedNode": "payments-servicebus",
            "affectedNodes": ["order-function", "api-management"],
            "affectedEdges": [{"source": "order-function", "target": "payments-servicebus"}],
            "timestamp": "2026-06-26T10:00:00Z"
        }
        """;
        var result = JsonSerializer.Deserialize<BlastRadiusResult>(json, WebOptions);
        Assert.NotNull(result);
        Assert.Equal("payments-servicebus", result.FailedNode);
        Assert.Equal(2, result.AffectedNodes.Count);
        Assert.Contains("order-function", result.AffectedNodes);
        Assert.Single(result.AffectedEdges);
    }

    [Fact]
    public void Deserialize_GraphData_FromCamelCaseJson()
    {
        var json = """
        {
            "applications": [
                {"id": "INT-PAY-01", "title": "Payments Processing"}
            ],
            "nodes": [
                {"id": "payments-servicebus", "label": "Payments Service Bus", "azureType": "service-bus", "appIds": ["INT-PAY-01"], "criticality": "high"}
            ],
            "edges": [
                {"source": "order-function", "target": "payments-servicebus"}
            ]
        }
        """;
        var result = JsonSerializer.Deserialize<GraphData>(json, WebOptions);
        Assert.NotNull(result);
        Assert.Single(result.Applications);
        Assert.Equal("INT-PAY-01", result.Applications[0].Id);
        Assert.Equal("Payments Processing", result.Applications[0].Title);
        Assert.Single(result.Nodes);
        Assert.Equal("payments-servicebus", result.Nodes[0].Id);
        Assert.Equal("service-bus", result.Nodes[0].AzureType);
        Assert.Contains("INT-PAY-01", result.Nodes[0].AppIds);
        Assert.Single(result.Edges);
    }

    [Fact]
    public void Deserialize_ServiceNode_AllProperties()
    {
        var json = """{"id": "cosmos-db", "label": "Cosmos DB", "azureType": "cosmos-db", "appIds": ["SHARED"], "criticality": "high"}""";
        var node = JsonSerializer.Deserialize<ServiceNode>(json, WebOptions);
        Assert.NotNull(node);
        Assert.Equal("cosmos-db", node.Id);
        Assert.Equal("Cosmos DB", node.Label);
        Assert.Equal("cosmos-db", node.AzureType);
        Assert.Contains("SHARED", node.AppIds);
        Assert.Equal("high", node.Criticality);
    }

    [Fact]
    public void Deserialize_ApplicationInfo()
    {
        var json = """{"id": "INT-35", "title": "Create SO"}""";
        var app = JsonSerializer.Deserialize<ApplicationInfo>(json, WebOptions);
        Assert.NotNull(app);
        Assert.Equal("INT-35", app.Id);
        Assert.Equal("Create SO", app.Title);
    }

    [Fact]
    public void Deserialize_DependencyEdge()
    {
        var json = """{"source": "order-function", "target": "payments-servicebus"}""";
        var edge = JsonSerializer.Deserialize<DependencyEdge>(json, WebOptions);
        Assert.NotNull(edge);
        Assert.Equal("order-function", edge.Source);
        Assert.Equal("payments-servicebus", edge.Target);
    }

    [Fact]
    public void Deserialize_SignalRNegotiateResponse()
    {
        var json = """{"url": "https://myservice.service.signalr.net/client", "accessToken": "eyJhbGciOiJIUz..."}""";
        var response = JsonSerializer.Deserialize<SignalRNegotiateResponse>(json, WebOptions);
        Assert.NotNull(response);
        Assert.Equal("https://myservice.service.signalr.net/client", response.Url);
        Assert.Equal("eyJhbGciOiJIUz...", response.AccessToken);
    }

    [Fact]
    public void Deserialize_BlastRadiusResult_EmptyAffectedNodes()
    {
        var json = """
        {
            "failedNode": "api-management",
            "affectedNodes": [],
            "affectedEdges": [],
            "timestamp": "2026-06-26T10:00:00Z"
        }
        """;
        var result = JsonSerializer.Deserialize<BlastRadiusResult>(json, WebOptions);
        Assert.NotNull(result);
        Assert.Empty(result.AffectedNodes);
        Assert.Empty(result.AffectedEdges);
    }
}
