namespace BlastRadiusUI.Models;

public record ApplicationInfo(string Id, string Title);

public record ServiceNode(string Id, string Label, string AzureType, List<string> AppIds, string Criticality);

public record DependencyEdge(string Source, string Target);

public record GraphData(List<ApplicationInfo> Applications, List<ServiceNode> Nodes, List<DependencyEdge> Edges);

public record BlastRadiusResult(
    string FailedNode,
    List<string> AffectedNodes,
    List<DependencyEdge> AffectedEdges,
    DateTimeOffset Timestamp);

public record SignalRNegotiateResponse(string Url, string AccessToken);
