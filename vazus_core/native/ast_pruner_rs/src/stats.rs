/// Statistics telemetry for AST pruning matching Python ASTPruner schema.

#[derive(Debug, Clone)]
pub struct PruningStats {
    pub is_valid: bool,
    pub language: &'static str,
    pub total_nodes: usize,
    pub pruned_nodes: usize,
    pub nodes_removed: usize,
    pub reduction_percent: f64,
    pub reduction_percentage: f64,
    pub orig_bytes: usize,
    pub pruned_bytes: usize,
}

impl PruningStats {
    pub fn new(total_nodes: usize, pruned_nodes: usize, orig_bytes: usize, pruned_bytes: usize, is_valid: bool) -> Self {
        let nodes_removed = if total_nodes > pruned_nodes {
            total_nodes - pruned_nodes
        } else {
            0
        };
        let node_reduction = if total_nodes > 0 {
            (nodes_removed as f64 / total_nodes as f64) * 100.0
        } else {
            0.0
        };
        let byte_reduction = if orig_bytes > 0 && orig_bytes > pruned_bytes {
            ((orig_bytes - pruned_bytes) as f64 / orig_bytes as f64) * 100.0
        } else {
            0.0
        };
        let reduction_pct = ((node_reduction.max(byte_reduction)) * 100.0).round() / 100.0;


        Self {
            is_valid,
            language: "python",
            total_nodes,
            pruned_nodes,
            nodes_removed,
            reduction_percent: reduction_pct,
            reduction_percentage: reduction_pct,
            orig_bytes,
            pruned_bytes,
        }
    }
}
