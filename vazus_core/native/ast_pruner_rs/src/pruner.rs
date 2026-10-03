use std::cell::RefCell;
use std::collections::HashSet;
use tree_sitter::{Language, Node, Parser, Tree};
use crate::stats::PruningStats;

thread_local! {
    /// Thread-local Tree-sitter Python parser instance.
    /// Initialized lazily once per OS thread; reused across all pruning calls.
    static PYTHON_PARSER: RefCell<Parser> = RefCell::new({
        let mut parser = Parser::new();
        let lang: Language = tree_sitter_python::LANGUAGE.into();
        parser
            .set_language(&lang)
            .expect("Failed to initialize tree-sitter Python language in thread-local storage");
        parser
    });
}

/// Parses Python source code using the thread-local Tree-sitter parser.
/// Reuses parser state across calls on the same thread without reallocation.
pub fn parse_python(source: &str) -> Option<Tree> {
    PYTHON_PARSER.with(|cell| {
        let mut parser = cell.borrow_mut();
        parser.parse(source, None)
    })
}

/// Counts total AST nodes in the tree using a single reusable cursor.
/// Executes in O(N) time with O(1) heap allocations and zero stack recursion risk.
pub fn count_tree_nodes_cursor(tree: &Tree) -> usize {
    let mut cursor = tree.walk();
    let mut count = 0;
    loop {
        count += 1;
        if cursor.goto_first_child() {
            continue;
        }
        if cursor.goto_next_sibling() {
            continue;
        }
        let mut ascended = false;
        while cursor.goto_parent() {
            if cursor.goto_next_sibling() {
                ascended = true;
                break;
            }
        }
        if !ascended {
            break;
        }
    }
    count
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DocstringMode {
    None,
    Full,
    Summary,
}

impl DocstringMode {
    pub fn from_str(s: &str) -> Self {
        match s {
            "none" => DocstringMode::None,
            "full" => DocstringMode::Full,
            _ => DocstringMode::Summary,
        }
    }
}

/// Normalizes spaces around '=' in parameter signatures to match Python ast.unparse format (e.g. `x: int=64`).
pub fn normalize_param_defaults(sig: &str) -> String {
    if !sig.contains('=') {
        return sig.to_string();
    }
    let bytes = sig.as_bytes();
    let len = bytes.len();
    let mut out = Vec::with_capacity(len);
    let mut i = 0;
    let mut in_single_quote = false;
    let mut in_double_quote = false;
    let mut escape = false;

    while i < len {
        let b = bytes[i];
        if escape {
            out.push(b);
            escape = false;
            i += 1;
            continue;
        }

        if b == b'\\' {
            escape = true;
            out.push(b);
            i += 1;
            continue;
        }

        if b == b'\'' && !in_double_quote {
            in_single_quote = !in_single_quote;
            out.push(b);
            i += 1;
            continue;
        }

        if b == b'"' && !in_single_quote {
            in_double_quote = !in_double_quote;
            out.push(b);
            i += 1;
            continue;
        }

        if !in_single_quote && !in_double_quote && b == b'=' {
            while out.last() == Some(&b' ') {
                out.pop();
            }
            out.push(b'=');
            i += 1;
            while i < len && bytes[i] == b' ' {
                i += 1;
            }
            continue;
        }

        out.push(b);
        i += 1;
    }

    String::from_utf8(out).unwrap_or_else(|_| sig.to_string())
}


/// Process a docstring according to the requested DocstringMode.
pub fn process_docstring(raw_doc: &str, mode: DocstringMode) -> Option<String> {
    if mode == DocstringMode::None {
        return None;
    }

    let trimmed = raw_doc.trim();
    let content = if trimmed.starts_with("\"\"\"") && trimmed.ends_with("\"\"\"") && trimmed.len() >= 6 {
        &trimmed[3..trimmed.len() - 3]
    } else if trimmed.starts_with("'''") && trimmed.ends_with("'''") && trimmed.len() >= 6 {
        &trimmed[3..trimmed.len() - 3]
    } else if trimmed.starts_with('"') && trimmed.ends_with('"') && trimmed.len() >= 2 {
        &trimmed[1..trimmed.len() - 1]
    } else if trimmed.starts_with('\'') && trimmed.ends_with('\'') && trimmed.len() >= 2 {
        &trimmed[1..trimmed.len() - 1]
    } else {
        trimmed
    };

    if mode == DocstringMode::Full {
        return Some(format!("\"\"\"{}\"\"\"", content));
    }

    // DocstringMode::Summary
    let lines: Vec<&str> = content
        .lines()
        .map(|l| l.trim())
        .filter(|l| !l.is_empty())
        .collect();

    if lines.is_empty() {
        return None;
    }

    let contract_lines: Vec<&str> = lines
        .iter()
        .copied()
        .filter(|l| l.starts_with(":requires:") || l.starts_with(":ensures:"))
        .collect();

    let non_contract_lines: Vec<&str> = lines
        .iter()
        .copied()
        .filter(|l| !l.starts_with(":requires:") && !l.starts_with(":ensures:"))
        .collect();

    if !contract_lines.is_empty() {
        let summary = non_contract_lines.first().copied().unwrap_or("");
        if !summary.is_empty() {
            Some(format!("\"\"\"{}\n{}\"\"\"", summary, contract_lines.join("\n")))
        } else {
            Some(format!("\"\"\"{}\"\"\"", contract_lines.join("\n")))
        }
    } else {
        let summary = lines[0];
        Some(format!("\"\"\"{}\"\"\"", summary))
    }
}

/// Check Python syntax validity using the thread-local tree-sitter parser.
pub fn check_python_syntax(source: &str) -> bool {
    if let Some(tree) = parse_python(source) {
        return !tree.root_node().has_error();
    }
    check_delimiters_balanced(source)
}

/// Count AST nodes in Python code using the thread-local tree-sitter parser.
pub fn count_tree_nodes(code: &str) -> usize {
    if let Some(tree) = parse_python(code) {
        let count = count_tree_nodes_cursor(&tree);
        if count > 0 {
            return count;
        }
    }
    estimate_ast_nodes(code)
}

/// Fallback delimiter balance checker.
pub fn check_delimiters_balanced(source: &str) -> bool {
    let mut stack = Vec::new();
    let mut in_single = false;
    let mut in_double = false;
    let mut in_triple_single = false;
    let mut in_triple_double = false;
    let mut escaped = false;
    let chars: Vec<char> = source.chars().collect();
    let len = chars.len();
    let mut i = 0;

    while i < len {
        let c = chars[i];
        if escaped {
            escaped = false;
            i += 1;
            continue;
        }
        if c == '\\' {
            escaped = true;
            i += 1;
            continue;
        }
        if !in_single && !in_double {
            if !in_triple_double && i + 2 < len && c == '\'' && chars[i + 1] == '\'' && chars[i + 2] == '\'' {
                in_triple_single = !in_triple_single;
                i += 3;
                continue;
            }
            if !in_triple_single && i + 2 < len && c == '"' && chars[i + 1] == '"' && chars[i + 2] == '"' {
                in_triple_double = !in_triple_double;
                i += 3;
                continue;
            }
        }
        if in_triple_single || in_triple_double {
            i += 1;
            continue;
        }
        if !in_single && !in_double && c == '#' {
            while i < len && chars[i] != '\n' {
                i += 1;
            }
            continue;
        }
        if !in_double && c == '\'' {
            in_single = !in_single;
            i += 1;
            continue;
        }
        if !in_single && c == '"' {
            in_double = !in_double;
            i += 1;
            continue;
        }
        if in_single || in_double {
            i += 1;
            continue;
        }
        match c {
            '(' | '[' | '{' => stack.push(c),
            ')' => {
                if stack.pop() != Some('(') {
                    return false;
                }
            }
            ']' => {
                if stack.pop() != Some('[') {
                    return false;
                }
            }
            '}' => {
                if stack.pop() != Some('{') {
                    return false;
                }
            }
            _ => {}
        }
        i += 1;
    }
    stack.is_empty() && !in_single && !in_double && !in_triple_single && !in_triple_double
}

/// Finds the byte index of the header-terminating colon at bracket depth 0 outside quotes and comments.
pub fn find_header_colon(s: &str) -> Option<usize> {
    let mut in_single = false;
    let mut in_double = false;
    let mut escaped = false;
    let mut open_brackets: usize = 0;

    for (byte_idx, c) in s.char_indices() {
        if escaped {
            escaped = false;
            continue;
        }
        if c == '\\' {
            escaped = true;
            continue;
        }
        if in_single {
            if c == '\'' {
                in_single = false;
            }
            continue;
        }
        if in_double {
            if c == '"' {
                in_double = false;
            }
            continue;
        }
        if c == '\'' {
            in_single = true;
        } else if c == '"' {
            in_double = true;
        } else if c == '(' || c == '[' || c == '{' {
            open_brackets += 1;
        } else if c == ')' || c == ']' || c == '}' {
            open_brackets = open_brackets.saturating_sub(1);
        } else if c == '#' {
            break;
        } else if c == ':' && open_brackets == 0 {
            return Some(byte_idx);
        }
    }
    None
}

/// Strip comment from a string slice outside quotes.
pub fn strip_comment(s: &str) -> &str {
    let mut in_single = false;
    let mut in_double = false;
    let mut escaped = false;

    for (byte_idx, c) in s.char_indices() {
        if escaped {
            escaped = false;
            continue;
        }
        if c == '\\' {
            escaped = true;
            continue;
        }
        if in_single {
            if c == '\'' {
                in_single = false;
            }
            continue;
        }
        if in_double {
            if c == '"' {
                in_double = false;
            }
            continue;
        }
        if c == '\'' {
            in_single = true;
        } else if c == '"' {
            in_double = true;
        } else if c == '#' {
            return s[..byte_idx].trim();
        }
    }
    s.trim()
}

/// Estimate AST nodes count from Python code based on token density.
pub fn estimate_ast_nodes(code: &str) -> usize {
    let mut count = 1; // module
    for line in code.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        let words = trimmed.split(|c: char| c.is_whitespace() || ",=():+-*/.[]{}<>\"'".contains(c)).filter(|s| !s.is_empty()).count();
        count += words.max(1);
    }
    count
}

/// Splits large Python source files (> 32 KB) into independent top-level statement chunks.
/// Splits occur at line boundaries starting at column 0 outside quotes and brackets.
pub fn split_python_source_chunks<'a>(source: &'a str, min_chunk_size: usize) -> Vec<&'a str> {
    if source.len() < min_chunk_size * 2 {
        return vec![source];
    }

    let mut chunks = Vec::new();
    let mut chunk_start = 0;
    let mut in_single_quote = false;
    let mut in_double_quote = false;
    let mut in_triple_single = false;
    let mut in_triple_double = false;
    let mut open_brackets: usize = 0;
    let mut escaped = false;

    let bytes = source.as_bytes();
    let len = bytes.len();
    let mut i = 0;

    while i < len {
        let b = bytes[i];
        if escaped {
            escaped = false;
            i += 1;
            continue;
        }

        if b == b'\\' {
            escaped = true;
            i += 1;
            continue;
        }

        // Handle triple quotes outside single quotes
        if !in_single_quote && !in_double_quote {
            if !in_triple_double && i + 2 < len && b == b'\'' && bytes[i + 1] == b'\'' && bytes[i + 2] == b'\'' {
                in_triple_single = !in_triple_single;
                i += 3;
                continue;
            }
            if !in_triple_single && i + 2 < len && b == b'"' && bytes[i + 1] == b'"' && bytes[i + 2] == b'"' {
                in_triple_double = !in_triple_double;
                i += 3;
                continue;
            }
        }

        if in_triple_single || in_triple_double {
            i += 1;
            continue;
        }

        // Handle single and double quotes
        if !in_double_quote && b == b'\'' {
            in_single_quote = !in_single_quote;
            i += 1;
            continue;
        }
        if !in_single_quote && b == b'"' {
            in_double_quote = !in_double_quote;
            i += 1;
            continue;
        }

        if in_single_quote || in_double_quote {
            i += 1;
            continue;
        }

        // Handle brackets
        if b == b'(' || b == b'[' || b == b'{' {
            open_brackets += 1;
        } else if b == b')' || b == b']' || b == b'}' {
            open_brackets = open_brackets.saturating_sub(1);
        } else if b == b'\n' && open_brackets == 0 {
            let next_i = i + 1;
            if next_i - chunk_start >= min_chunk_size && next_i < len {
                let rest = &source[next_i..];
                if rest.starts_with("def ")
                    || rest.starts_with("async def ")
                    || rest.starts_with("class ")
                    || rest.starts_with('@')
                {
                    chunks.push(&source[chunk_start..next_i]);
                    chunk_start = next_i;
                }
            }
        }

        i += 1;
    }

    if chunk_start < len {
        if chunks.is_empty() {
            chunks.push(source);
        } else {
            chunks.push(&source[chunk_start..]);
        }
    }

    chunks
}

// ==============================================================================
// Native Tree-Sitter CST Traversal Engine
// ==============================================================================

/// High-throughput Native Tree-Sitter CST pruner.
pub struct NativeTreeSitterPruner {

    docstring_mode: DocstringMode,
}

pub type FastASTPruner = NativeTreeSitterPruner;

impl NativeTreeSitterPruner {
    pub fn new(docstring_mode: DocstringMode) -> Self {
        Self { docstring_mode }
    }

    pub fn prune(&self, source: &str) -> (String, PruningStats) {
        let orig_bytes = source.as_bytes().len();

        // 1. Handle empty input
        if source.trim().is_empty() {
            let stats = PruningStats::new(0, 0, orig_bytes, 0, true);
            return (String::new(), stats);
        }

        // 2. Multi-chunk parallel acceleration for large modules (> 8 KB)
        let chunks = split_python_source_chunks(source, 4_000);
        if chunks.len() > 1 {
            use rayon::prelude::*;
            let results: Vec<(String, PruningStats)> = chunks
                .into_par_iter()
                .map(|chunk| self.prune_single_chunk(chunk))
                .collect();

            let mut out = String::with_capacity(orig_bytes);
            let mut total_nodes = 0;
            let mut pruned_nodes = 0;
            let mut all_valid = true;

            for (idx, (pruned, stats)) in results.iter().enumerate() {
                if !stats.is_valid {
                    all_valid = false;
                }
                total_nodes += stats.total_nodes;
                pruned_nodes += stats.pruned_nodes;
                if !pruned.is_empty() {
                    if idx > 0 && !out.is_empty() {
                        out.push('\n');
                    }
                    out.push_str(pruned);
                    out.push('\n');
                }
            }

            let pruned_code = out.trim_end().to_string();
            let pruned_bytes = pruned_code.as_bytes().len();
            let combined_stats = PruningStats::new(
                total_nodes,
                pruned_nodes,
                orig_bytes,
                pruned_bytes,
                all_valid,
            );
            return (pruned_code, combined_stats);
        }

        self.prune_single_chunk(source)
    }

    pub fn prune_single_chunk(&self, source: &str) -> (String, PruningStats) {
        let orig_bytes = source.as_bytes().len();

        if source.trim().is_empty() {
            let stats = PruningStats::new(0, 0, orig_bytes, 0, true);
            return (String::new(), stats);
        }


        // 2. Parse source code ONCE using the thread-local parser
        let (tree, orig_nodes) = match parse_python(source) {
            Some(t) => {
                let root = t.root_node();
                if root.has_error() {
                    let stats = PruningStats::new(0, 0, orig_bytes, orig_bytes, false);
                    return (source.to_string(), stats);
                }
                let nodes = count_tree_nodes_cursor(&t);
                (t, nodes)
            }
            None => {
                let stats = PruningStats::new(0, 0, orig_bytes, orig_bytes, false);
                return (source.to_string(), stats);
            }
        };

        let root = tree.root_node();

        // 3. CST traversal to synthesize pruned skeleton
        let mut out = String::with_capacity(orig_bytes / 2);
        let mut top_level_items: Vec<(String, Option<&str>, usize)> = Vec::new();
        let mut total_removed_nodes = 0;
        let mut has_emitted_module_doc = false;

        let mut cursor = root.walk();
        for child in root.children(&mut cursor) {
            // Check module docstring
            if !has_emitted_module_doc && is_docstring_expr(&child) && top_level_items.is_empty() {
                has_emitted_module_doc = true;
                if let Some(doc_str) = self.extract_docstring(&child, source) {
                    top_level_items.push((doc_str, None, 0));
                } else {
                    total_removed_nodes += count_node_sub_tree(&child);
                }
                continue;
            }

            match child.kind() {
                "comment" => {
                    total_removed_nodes += count_node_sub_tree(&child);
                }
                "function_definition" => {
                    has_emitted_module_doc = true;
                    if let Some((rendered, name, rem)) = self.prune_function(&child, source, &[], 0) {
                        top_level_items.push((rendered, Some(name), rem));
                    } else {
                        total_removed_nodes += count_node_sub_tree(&child);
                    }
                }
                "class_definition" => {
                    has_emitted_module_doc = true;
                    if let Some((rendered, name, rem)) = self.prune_class(&child, source, &[], 0) {
                        top_level_items.push((rendered, Some(name), rem));
                    } else {
                        total_removed_nodes += count_node_sub_tree(&child);
                    }
                }
                "decorated_definition" => {
                    has_emitted_module_doc = true;
                    let (decorators, def_node) = self.collect_decorators(&child, source);
                    if let Some(def) = def_node {
                        match def.kind() {
                            "function_definition" => {
                                if let Some((rendered, name, rem)) = self.prune_function(&def, source, &decorators, 0) {
                                    top_level_items.push((rendered, Some(name), rem));
                                } else {
                                    total_removed_nodes += count_node_sub_tree(&child);
                                }
                            }
                            "class_definition" => {
                                if let Some((rendered, name, rem)) = self.prune_class(&def, source, &decorators, 0) {
                                    top_level_items.push((rendered, Some(name), rem));
                                } else {
                                    total_removed_nodes += count_node_sub_tree(&child);
                                }
                            }
                            _ => {
                                total_removed_nodes += count_node_sub_tree(&child);
                            }
                        }
                    } else {
                        total_removed_nodes += count_node_sub_tree(&child);
                    }
                }
                "expression_statement" => {
                    has_emitted_module_doc = true;
                    if is_private_assignment(&child, source) {
                        total_removed_nodes += count_node_sub_tree(&child);
                    } else {
                        let stmt = &source[child.start_byte()..child.end_byte()];
                        top_level_items.push((stmt.to_string(), None, 0));
                    }
                }
                _ => {
                    has_emitted_module_doc = true;
                    let stmt = &source[child.start_byte()..child.end_byte()];
                    top_level_items.push((stmt.to_string(), None, 0));
                }
            }
        }

        // 4. Reverse deduplication for top-level functions
        let mut seen = HashSet::new();
        let mut final_items = Vec::new();
        for (item, name_opt, rem) in top_level_items.into_iter().rev() {
            if let Some(name) = name_opt {
                if seen.contains(name) {
                    total_removed_nodes += rem + 10;
                    continue;
                }
                seen.insert(name);
            }
            total_removed_nodes += rem;
            final_items.push(item);
        }
        final_items.reverse();

        for (idx, item) in final_items.iter().enumerate() {
            if idx > 0 {
                out.push('\n');
            }
            out.push_str(item);
            out.push('\n');
        }

        let pruned_code = out.trim_end().to_string();
        let pruned_bytes = pruned_code.as_bytes().len();

        let pruned_nodes = if pruned_code.trim().is_empty() {
            0
        } else {
            orig_nodes.saturating_sub(total_removed_nodes).max(1)
        };

        let stats = PruningStats::new(orig_nodes, pruned_nodes, orig_bytes, pruned_bytes, true);
        (pruned_code, stats)
    }

    fn collect_decorators<'a>(&self, node: &Node<'a>, source: &'a str) -> (Vec<&'a str>, Option<Node<'a>>) {
        let mut decs = Vec::new();
        let mut def = None;
        let mut cur = node.walk();
        for child in node.children(&mut cur) {
            if child.kind() == "decorator" {
                decs.push(&source[child.start_byte()..child.end_byte()]);
            } else if child.kind() == "function_definition" || child.kind() == "class_definition" {
                def = Some(child);
            }
        }
        (decs, def)
    }

    fn extract_docstring(&self, expr_stmt: &Node, source: &str) -> Option<String> {
        let mut cur = expr_stmt.walk();
        for child in expr_stmt.named_children(&mut cur) {
            if child.kind() == "string" {
                let raw_doc = &source[child.start_byte()..child.end_byte()];
                return process_docstring(raw_doc, self.docstring_mode);
            }
        }
        None
    }

    fn prune_function<'a>(
        &self,
        node: &Node<'a>,
        source: &'a str,
        decorators: &[&'a str],
        indent_col: usize,
    ) -> Option<(String, &'a str, usize)> {
        let name_node = node.child_by_field_name("name")?;
        let name = &source[name_node.start_byte()..name_node.end_byte()];

        // Filter private functions (starts with _ and not __)
        if name.starts_with('_') && !name.starts_with("__") {
            return None;
        }

        let body_node = node.child_by_field_name("body")?;
        let colon_node = find_colon_before(node, &body_node)?;
        let raw_sig = &source[node.start_byte()..colon_node.end_byte()];
        let norm_sig = normalize_param_defaults(raw_sig);

        let indent_str = " ".repeat(indent_col);
        let body_indent_step = determine_indent_step(node, &body_node, indent_col);
        let body_indent_str = " ".repeat(indent_col + body_indent_step);

        let mut buf = String::new();
        for dec in decorators {
            for (line_idx, line) in dec.lines().enumerate() {
                if line_idx == 0 {
                    buf.push_str(&indent_str);
                }
                buf.push_str(line);
                buf.push('\n');
            }
        }
        buf.push_str(&indent_str);
        buf.push_str(&norm_sig);
        buf.push('\n');

        let mut removed_nodes = 0;
        let mut cur = body_node.walk();
        let mut doc_node_id = None;

        for child in body_node.named_children(&mut cur) {
            if is_docstring_expr(&child) {
                doc_node_id = Some(child.id());
                if let Some(doc_str) = self.extract_docstring(&child, source) {
                    for line in doc_str.lines() {
                        buf.push_str(&body_indent_str);
                        buf.push_str(line);
                        buf.push('\n');
                    }
                } else {
                    removed_nodes += count_node_sub_tree(&child);
                }
                break;
            } else if child.kind() != "comment" {
                break;
            }
        }

        // Extract return statement or emit ellipsis
        let ret_stmt = find_first_return_in_block(&body_node, source);
        let mut ret_node_id = None;
        if let Some(ret_str) = ret_stmt {
            for (line_idx, line) in ret_str.lines().enumerate() {
                if line_idx == 0 {
                    buf.push_str(&body_indent_str);
                }
                buf.push_str(line);
                buf.push('\n');
            }
        } else {
            buf.push_str(&body_indent_str);
            buf.push_str("...\n");
        }

        // Count removed statements and comments in body
        let mut cur2 = body_node.walk();
        for child in body_node.children(&mut cur2) {
            let cid = child.id();
            if Some(cid) == doc_node_id {
                continue;
            }
            if child.kind() == "return_statement" && ret_node_id.is_none() {
                ret_node_id = Some(cid);
                continue;
            }
            if child.kind() != "{" && child.kind() != "}" && child.kind() != ":" {
                removed_nodes += count_node_sub_tree(&child);
            }
        }


        Some((buf.trim_end().to_string(), name, removed_nodes))
    }

    fn prune_class<'a>(
        &self,
        node: &Node<'a>,
        source: &'a str,
        decorators: &[&'a str],
        indent_col: usize,
    ) -> Option<(String, &'a str, usize)> {
        let name_node = node.child_by_field_name("name")?;
        let name = &source[name_node.start_byte()..name_node.end_byte()];

        let body_node = node.child_by_field_name("body")?;
        let colon_node = find_colon_before(node, &body_node)?;
        let raw_class_header = &source[node.start_byte()..colon_node.end_byte()];

        let indent_str = " ".repeat(indent_col);
        let body_indent_step = determine_indent_step(node, &body_node, indent_col);
        let body_col = indent_col + body_indent_step;
        let body_indent_str = " ".repeat(body_col);

        let mut buf = String::new();
        for dec in decorators {
            for (line_idx, line) in dec.lines().enumerate() {
                if line_idx == 0 {
                    buf.push_str(&indent_str);
                }
                buf.push_str(line);
                buf.push('\n');
            }
        }
        buf.push_str(&indent_str);
        buf.push_str(raw_class_header);
        buf.push('\n');

        let mut class_items: Vec<(String, Option<&'a str>, usize)> = Vec::new();
        let mut class_removed_nodes = 0;
        let mut cur = body_node.walk();

        let mut has_class_doc = false;
        for child in body_node.children(&mut cur) {
            if !has_class_doc && is_docstring_expr(&child) && class_items.is_empty() {
                has_class_doc = true;
                if let Some(doc_str) = self.extract_docstring(&child, source) {
                    let mut doc_buf = String::new();
                    for line in doc_str.lines() {
                        doc_buf.push_str(&body_indent_str);
                        doc_buf.push_str(line);
                        doc_buf.push('\n');
                    }
                    class_items.push((doc_buf.trim_end().to_string(), None, 0));
                } else {
                    class_removed_nodes += count_node_sub_tree(&child);
                }
                continue;
            }

            match child.kind() {
                "function_definition" => {
                    if let Some((rendered, m_name, rem)) = self.prune_function(&child, source, &[], body_col) {
                        class_items.push((rendered, Some(m_name), rem));
                    } else {
                        class_removed_nodes += count_node_sub_tree(&child);
                    }
                }
                "class_definition" => {
                    if let Some((rendered, inner_name, rem)) = self.prune_class(&child, source, &[], body_col) {
                        class_items.push((rendered, Some(inner_name), rem));
                    } else {
                        class_removed_nodes += count_node_sub_tree(&child);
                    }
                }
                "decorated_definition" => {
                    let (decs, def_opt) = self.collect_decorators(&child, source);
                    if let Some(def) = def_opt {
                        match def.kind() {
                            "function_definition" => {
                                if let Some((rendered, m_name, rem)) = self.prune_function(&def, source, &decs, body_col) {
                                    class_items.push((rendered, Some(m_name), rem));
                                } else {
                                    class_removed_nodes += count_node_sub_tree(&child);
                                }
                            }
                            "class_definition" => {
                                if let Some((rendered, inner_name, rem)) = self.prune_class(&def, source, &decs, body_col) {
                                    class_items.push((rendered, Some(inner_name), rem));
                                } else {
                                    class_removed_nodes += count_node_sub_tree(&child);
                                }
                            }
                            _ => {
                                class_removed_nodes += count_node_sub_tree(&child);
                            }
                        }
                    } else {
                        class_removed_nodes += count_node_sub_tree(&child);
                    }
                }
                "expression_statement" => {
                    if is_private_assignment(&child, source) {
                        class_removed_nodes += count_node_sub_tree(&child);
                    } else {
                        let stmt_str = &source[child.start_byte()..child.end_byte()];
                        let mut s = String::new();
                        for (line_idx, line) in stmt_str.lines().enumerate() {
                            if line_idx == 0 {
                                s.push_str(&body_indent_str);
                            }
                            s.push_str(line);
                            s.push('\n');
                        }
                        class_items.push((s.trim_end().to_string(), None, 0));
                    }
                }
                "comment" => {
                    class_removed_nodes += count_node_sub_tree(&child);
                }
                _ => {
                    if child.kind() != "{" && child.kind() != "}" && child.kind() != ":" {
                        class_removed_nodes += count_node_sub_tree(&child);
                    }
                }
            }
        }


        // Method deduplication in class
        let mut seen = HashSet::new();
        let mut final_items = Vec::new();
        for (item, m_name_opt, rem) in class_items.into_iter().rev() {
            if let Some(m_name) = m_name_opt {
                if seen.contains(m_name) {
                    class_removed_nodes += rem + 10;
                    continue;
                }
                seen.insert(m_name);
            }
            class_removed_nodes += rem;
            final_items.push(item);
        }
        final_items.reverse();

        if final_items.is_empty() {
            buf.push_str(&body_indent_str);
            buf.push_str("...\n");
        } else {
            for item in final_items {
                buf.push_str(&item);
                buf.push('\n');
            }
        }

        Some((buf.trim_end().to_string(), name, class_removed_nodes))
    }
}

fn count_node_sub_tree(node: &Node) -> usize {
    let mut count = 1;
    let mut cur = node.walk();
    for child in node.children(&mut cur) {
        count += count_node_sub_tree(&child);
    }
    count
}

fn find_colon_before<'a>(node: &'a Node<'a>, body_node: &Node<'a>) -> Option<Node<'a>> {
    let mut cur = node.walk();
    for child in node.children(&mut cur) {
        if child.kind() == ":" && child.end_byte() <= body_node.start_byte() {
            return Some(child);
        }
    }
    None
}

fn determine_indent_step(node: &Node, body_node: &Node, parent_indent: usize) -> usize {
    if body_node.start_position().row == node.start_position().row {
        return 4;
    }
    let mut cur = body_node.walk();
    for child in body_node.named_children(&mut cur) {
        if child.start_position().row > node.start_position().row {
            let child_col = child.start_position().column;
            if child_col > parent_indent {
                return (child_col - parent_indent).max(2);
            }
        }
    }
    4
}

fn is_docstring_expr(node: &Node) -> bool {
    if node.kind() == "expression_statement" {
        let mut cur = node.walk();
        for child in node.named_children(&mut cur) {
            if child.kind() == "string" {
                return true;
            }
        }
    }
    false
}

fn find_first_return_in_block<'a>(body_node: &Node<'a>, source: &'a str) -> Option<&'a str> {
    let mut cur = body_node.walk();
    for child in body_node.children(&mut cur) {
        if child.kind() == "return_statement" {
            return Some(&source[child.start_byte()..child.end_byte()]);
        }
    }
    None
}

fn is_private_assignment(node: &Node, source: &str) -> bool {
    if node.kind() == "expression_statement" {
        let mut cur = node.walk();
        for child in node.named_children(&mut cur) {
            if child.kind() == "assignment" {
                if let Some(left) = child.child_by_field_name("left") {
                    let target_name = &source[left.start_byte()..left.end_byte()];
                    let ident = target_name.split('.').last().unwrap_or(target_name).trim();
                    if ident.starts_with('_') && !ident.starts_with("__") {
                        return true;
                    }
                }
            }
        }
    }
    false
}
