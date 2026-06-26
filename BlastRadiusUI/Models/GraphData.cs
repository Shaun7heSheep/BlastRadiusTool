namespace BlastRadiusUI.Models;

public record ServiceNode(string Id, string Label, string AzureType, string App, string Criticality);

public record DependencyEdge(string Source, string Target);

public record GraphData(List<ServiceNode> Nodes, List<DependencyEdge> Edges);

public record BlastRadiusResult(
    string FailedNode,
    List<string> AffectedNodes,
    List<DependencyEdge> AffectedEdges,
    DateTimeOffset Timestamp);

public record SignalRNegotiateResponse(string Url, string AccessToken);
