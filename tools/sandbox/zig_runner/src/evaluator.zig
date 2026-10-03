const std = @import("std");
const builtin = @import("builtin");

const is_windows = builtin.os.tag == .windows;
const kernel32 = if (is_windows) struct {
    extern "kernel32" fn Sleep(dwMilliseconds: u32) callconv(.winapi) void;
} else struct {};

fn sleepMs(ms: u32) void {
    if (is_windows) {
        kernel32.Sleep(ms);
    } else {
        var i: usize = 0;
        while (i < 100000) : (i += 1) {
            std.mem.doNotOptimizeAway(i);
        }
    }
}

pub const EvalError = error{
    SyntaxError,
    DivisionByZero,
    OutOfMemory,
    ExecutionTimeout,
};

pub const ValueType = enum {
    none,
    integer,
    float,
    boolean,
    string,
};

pub const Value = struct {
    tag: ValueType,
    data: union {
        int_val: i64,
        float_val: f64,
        bool_val: bool,
        str_val: []const u8,
    },

    pub fn none() Value {
        return .{ .tag = .none, .data = .{ .int_val = 0 } };
    }

    pub fn integer(v: i64) Value {
        return .{ .tag = .integer, .data = .{ .int_val = v } };
    }

    pub fn float(v: f64) Value {
        return .{ .tag = .float, .data = .{ .float_val = v } };
    }

    pub fn boolean(v: bool) Value {
        return .{ .tag = .boolean, .data = .{ .bool_val = v } };
    }

    pub fn string(v: []const u8) Value {
        return .{ .tag = .string, .data = .{ .str_val = v } };
    }

    pub fn isTruthy(self: Value) bool {
        return switch (self.tag) {
            .none => false,
            .boolean => self.data.bool_val,
            .integer => self.data.int_val != 0,
            .float => self.data.float_val != 0.0,
            .string => self.data.str_val.len > 0,
        };
    }
};

pub const Var = struct {
    name: []const u8,
    val: Value,
};

const TokenType = enum {
    eof,
    newline,
    semicolon,
    number_int,
    number_float,
    string_lit,
    identifier,
    kw_while,
    kw_print,
    kw_true,
    kw_false,
    kw_if,
    kw_else,
    op_plus,
    op_minus,
    op_star,
    op_slash,
    op_percent,
    op_assign,
    op_eq,
    op_ne,
    op_lt,
    op_le,
    op_gt,
    op_ge,
    lparen,
    rparen,
    lbrace,
    rbrace,
    comma,
    invalid,
};

const Token = struct {
    tag: TokenType,
    lexeme: []const u8,
    start: usize = 0,
    int_val: i64 = 0,
    float_val: f64 = 0.0,
};

pub const Tokenizer = struct {
    source: []const u8,
    pos: usize = 0,

    pub fn init(src: []const u8) Tokenizer {
        return .{ .source = src, .pos = 0 };
    }

    fn peekChar(self: *Tokenizer) ?u8 {
        if (self.pos >= self.source.len) return null;
        return self.source[self.pos];
    }

    fn nextChar(self: *Tokenizer) ?u8 {
        if (self.pos >= self.source.len) return null;
        const c = self.source[self.pos];
        self.pos += 1;
        return c;
    }

    pub fn next(self: *Tokenizer) Token {
        while (self.peekChar()) |c| {
            if (c == ' ' or c == '\t' or c == '\r') {
                _ = self.nextChar();
                continue;
            }
            if (c == '#' or (c == '/' and self.pos + 1 < self.source.len and self.source[self.pos + 1] == '/')) {
                // Comment line
                while (self.peekChar()) |comment_c| {
                    if (comment_c == '\n') break;
                    _ = self.nextChar();
                }
                continue;
            }
            break;
        }

        if (self.pos >= self.source.len) {
            return .{ .tag = .eof, .lexeme = "", .start = self.pos };
        }

        const start = self.pos;
        const c = self.nextChar().?;

        var tok: Token = switch (c) {
            '\n' => .{ .tag = .newline, .lexeme = "\n" },
            ';' => .{ .tag = .semicolon, .lexeme = ";" },
            '(' => .{ .tag = .lparen, .lexeme = "(" },
            ')' => .{ .tag = .rparen, .lexeme = ")" },
            '{' => .{ .tag = .lbrace, .lexeme = "{" },
            '}' => .{ .tag = .rbrace, .lexeme = "}" },
            ',' => .{ .tag = .comma, .lexeme = "," },
            '+' => .{ .tag = .op_plus, .lexeme = "+" },
            '-' => .{ .tag = .op_minus, .lexeme = "-" },
            '*' => .{ .tag = .op_star, .lexeme = "*" },
            '/' => .{ .tag = .op_slash, .lexeme = "/" },
            '%' => .{ .tag = .op_percent, .lexeme = "%" },
            '=' => blk: {
                if (self.peekChar() == '=') {
                    _ = self.nextChar();
                    break :blk .{ .tag = .op_eq, .lexeme = "==" };
                }
                break :blk .{ .tag = .op_assign, .lexeme = "=" };
            },
            '!' => blk: {
                if (self.peekChar() == '=') {
                    _ = self.nextChar();
                    break :blk .{ .tag = .op_ne, .lexeme = "!=" };
                }
                break :blk .{ .tag = .invalid, .lexeme = self.source[start..self.pos] };
            },
            '<' => blk: {
                if (self.peekChar() == '=') {
                    _ = self.nextChar();
                    break :blk .{ .tag = .op_le, .lexeme = "<=" };
                }
                break :blk .{ .tag = .op_lt, .lexeme = "<" };
            },
            '>' => blk: {
                if (self.peekChar() == '=') {
                    _ = self.nextChar();
                    break :blk .{ .tag = .op_ge, .lexeme = ">=" };
                }
                break :blk .{ .tag = .op_gt, .lexeme = ">" };
            },
            '"', '\'' => blk: {
                const quote = c;
                const str_start = self.pos;
                while (self.peekChar()) |sc| {
                    if (sc == quote) {
                        const str_slice = self.source[str_start..self.pos];
                        _ = self.nextChar();
                        break :blk .{ .tag = .string_lit, .lexeme = str_slice };
                    }
                    _ = self.nextChar();
                }
                break :blk .{ .tag = .invalid, .lexeme = self.source[start..self.pos] };
            },
            '0'...'9' => blk: {
                var is_float = false;
                while (self.peekChar()) |nc| {
                    if (nc >= '0' and nc <= '9') {
                        _ = self.nextChar();
                    } else if (nc == '.' and !is_float) {
                        is_float = true;
                        _ = self.nextChar();
                    } else {
                        break;
                    }
                }
                const lex = self.source[start..self.pos];
                if (is_float) {
                    const fval = std.fmt.parseFloat(f64, lex) catch 0.0;
                    break :blk .{ .tag = .number_float, .lexeme = lex, .float_val = fval };
                } else {
                    const ival = std.fmt.parseInt(i64, lex, 10) catch 0;
                    break :blk .{ .tag = .number_int, .lexeme = lex, .int_val = ival };
                }
            },
            'a'...'z', 'A'...'Z', '_' => blk: {
                while (self.peekChar()) |ic| {
                    if ((ic >= 'a' and ic <= 'z') or (ic >= 'A' and ic <= 'Z') or (ic >= '0' and ic <= '9') or ic == '_') {
                        _ = self.nextChar();
                    } else {
                        break;
                    }
                }
                const lex = self.source[start..self.pos];
                if (std.mem.eql(u8, lex, "while")) break :blk .{ .tag = .kw_while, .lexeme = lex };
                if (std.mem.eql(u8, lex, "print")) break :blk .{ .tag = .kw_print, .lexeme = lex };
                if (std.mem.eql(u8, lex, "true")) break :blk .{ .tag = .kw_true, .lexeme = lex };
                if (std.mem.eql(u8, lex, "false")) break :blk .{ .tag = .kw_false, .lexeme = lex };
                if (std.mem.eql(u8, lex, "if")) break :blk .{ .tag = .kw_if, .lexeme = lex };
                if (std.mem.eql(u8, lex, "else")) break :blk .{ .tag = .kw_else, .lexeme = lex };
                break :blk .{ .tag = .identifier, .lexeme = lex };
            },
            else => .{ .tag = .invalid, .lexeme = self.source[start..self.pos] },
        };
        tok.start = start;
        return tok;
    }
};

pub const Evaluator = struct {
    allocator: std.mem.Allocator,
    variables: std.ArrayList(Var),
    stdout_buf: std.ArrayList(u8),
    tokenizer: Tokenizer,
    current_token: Token,
    max_loop_iterations: ?usize = null,

    pub fn init(allocator: std.mem.Allocator) Evaluator {
        return .{
            .allocator = allocator,
            .variables = .empty,
            .stdout_buf = .empty,
            .tokenizer = Tokenizer.init(""),
            .current_token = .{ .tag = .eof, .lexeme = "" },
            .max_loop_iterations = null,
        };
    }

    pub fn deinit(self: *Evaluator) void {
        self.variables.deinit(self.allocator);
        self.stdout_buf.deinit(self.allocator);
    }

    pub fn setVar(self: *Evaluator, name: []const u8, val: Value) !void {
        for (self.variables.items) |*v| {
            if (std.mem.eql(u8, v.name, name)) {
                v.val = val;
                return;
            }
        }
        try self.variables.append(self.allocator, .{ .name = name, .val = val });
    }

    pub fn getVar(self: *Evaluator, name: []const u8) ?Value {
        var i: usize = self.variables.items.len;
        while (i > 0) {
            i -= 1;
            if (std.mem.eql(u8, self.variables.items[i].name, name)) {
                return self.variables.items[i].val;
            }
        }
        return null;
    }

    fn advance(self: *Evaluator) void {
        self.current_token = self.tokenizer.next();
    }

    fn eatNewlines(self: *Evaluator) void {
        while (self.current_token.tag == .newline or self.current_token.tag == .semicolon) {
            self.advance();
        }
    }

    pub fn eval(self: *Evaluator, code: []const u8) EvalError!void {
        self.stdout_buf.clearRetainingCapacity();
        self.tokenizer = Tokenizer.init(code);
        self.advance();

        self.eatNewlines();

        // Empty code is a clean no-op
        if (self.current_token.tag == .eof) {
            return;
        }

        while (self.current_token.tag != .eof) {
            self.eatNewlines();
            if (self.current_token.tag == .eof) break;

            try self.statement();

            if (self.current_token.tag == .newline or self.current_token.tag == .semicolon) {
                self.eatNewlines();
            } else if (self.current_token.tag != .eof) {
                return error.SyntaxError;
            }
        }
    }

    fn statement(self: *Evaluator) EvalError!void {
        if (self.current_token.tag == .kw_while) {
            try self.whileStatement();
            return;
        }

        if (self.current_token.tag == .kw_print) {
            self.advance();
            var has_paren = false;
            if (self.current_token.tag == .lparen) {
                has_paren = true;
                self.advance();
            }

            const val = try self.expression();

            if (has_paren) {
                if (self.current_token.tag != .rparen) return error.SyntaxError;
                self.advance();
            }

            try self.formatValue(val);
            try self.stdout_buf.append(self.allocator, '\n');
            return;
        }

        // Check for identifier assignment: ident = expr
        if (self.current_token.tag == .identifier) {
            const ident_name = self.current_token.lexeme;
            // Peek next token without losing tokenizer state or parse as assignment
            const saved_pos = self.tokenizer.pos;
            const saved_token = self.current_token;

            self.advance();
            if (self.current_token.tag == .op_assign) {
                self.advance();
                const val = try self.expression();
                try self.setVar(ident_name, val);
                return;
            } else {
                // Backtrack and evaluate as expression
                self.tokenizer.pos = saved_pos;
                self.current_token = saved_token;
            }
        }

        // Expression statement
        const val = try self.expression();
        if (val.tag != .none) {
            try self.formatValue(val);
            try self.stdout_buf.append(self.allocator, '\n');
        }
    }

    fn evalStatements(self: *Evaluator, code: []const u8) EvalError!void {
        const saved_tokenizer = self.tokenizer;
        const saved_token = self.current_token;
        defer {
            self.tokenizer = saved_tokenizer;
            self.current_token = saved_token;
        }

        self.tokenizer = Tokenizer.init(code);
        self.advance();
        self.eatNewlines();

        if (self.current_token.tag == .eof) {
            return;
        }

        while (self.current_token.tag != .eof) {
            self.eatNewlines();
            if (self.current_token.tag == .eof) break;

            try self.statement();

            if (self.current_token.tag == .newline or self.current_token.tag == .semicolon) {
                self.eatNewlines();
            } else if (self.current_token.tag != .eof) {
                return error.SyntaxError;
            }
        }
    }

    fn whileStatement(self: *Evaluator) EvalError!void {
        self.advance(); // consume 'while'

        var has_paren = false;
        if (self.current_token.tag == .lparen) {
            has_paren = true;
            self.advance();
        }

        const cond_start_pos = self.tokenizer.pos;
        const cond_start_token = self.current_token;

        const cond = try self.expression();

        if (has_paren) {
            if (self.current_token.tag != .rparen) return error.SyntaxError;
            self.advance();
        }

        if (self.current_token.tag != .lbrace) {
            return error.SyntaxError;
        }

        // body_start_pos is character index immediately following '{'
        const body_start_pos = self.current_token.start + 1;

        self.advance(); // consume '{'

        // Scan tokens until matching closing '}'
        var brace_depth: usize = 1;
        var body_end_pos: usize = body_start_pos;

        while (self.current_token.tag != .eof) {
            if (self.current_token.tag == .lbrace) {
                brace_depth += 1;
            } else if (self.current_token.tag == .rbrace) {
                brace_depth -= 1;
                if (brace_depth == 0) {
                    body_end_pos = self.current_token.start;
                    break;
                }
            }
            self.advance();
        }

        if (brace_depth != 0) {
            return error.SyntaxError;
        }

        self.advance(); // consume closing '}'

        // Record clean post-loop parser state for resumption
        const after_loop_pos = self.tokenizer.pos;
        const after_loop_token = self.current_token;

        defer {
            self.tokenizer.pos = after_loop_pos;
            self.current_token = after_loop_token;
        }

        const body_code = self.tokenizer.source[body_start_pos..body_end_pos];

        if (cond.isTruthy()) {
            const is_const_infinite = (cond_start_token.tag == .kw_true) or
                (cond_start_token.tag == .number_int and cond_start_token.int_val != 0) or
                (cond_start_token.tag == .number_float and cond_start_token.float_val != 0.0);

            if (is_const_infinite) {
                var it: usize = 0;
                while (true) : (it += 1) {
                    if (self.max_loop_iterations) |max_it| {
                        if (it >= max_it) return error.ExecutionTimeout;
                    }
                    if (body_code.len > 0) {
                        try self.evalStatements(body_code);
                    }
                    sleepMs(10);
                }
            } else {
                var it_count: usize = 0;
                const max_it = self.max_loop_iterations orelse 100000;
                while (it_count < max_it) : (it_count += 1) {
                    if (it_count > 0) {
                        // Re-evaluate condition
                        self.tokenizer.pos = cond_start_pos;
                        self.current_token = cond_start_token;
                        const c = try self.expression();
                        if (!c.isTruthy()) break;
                    }

                    if (body_code.len > 0) {
                        try self.evalStatements(body_code);
                    }
                }
                if (it_count >= max_it) {
                    return error.ExecutionTimeout;
                }
            }
        }
    }

    fn expression(self: *Evaluator) EvalError!Value {
        return self.equality();
    }

    fn equality(self: *Evaluator) EvalError!Value {
        var left = try self.comparison();

        while (self.current_token.tag == .op_eq or self.current_token.tag == .op_ne) {
            const op = self.current_token.tag;
            self.advance();
            const right = try self.comparison();

            if (op == .op_eq) {
                left = Value.boolean(valuesEqual(left, right));
            } else {
                left = Value.boolean(!valuesEqual(left, right));
            }
        }
        return left;
    }

    fn comparison(self: *Evaluator) EvalError!Value {
        var left = try self.additive();

        while (self.current_token.tag == .op_lt or self.current_token.tag == .op_le or
            self.current_token.tag == .op_gt or self.current_token.tag == .op_ge)
        {
            const op = self.current_token.tag;
            self.advance();
            const right = try self.additive();

            const lf = toFloat(left);
            const rf = toFloat(right);
            left = switch (op) {
                .op_lt => Value.boolean(lf < rf),
                .op_le => Value.boolean(lf <= rf),
                .op_gt => Value.boolean(lf > rf),
                .op_ge => Value.boolean(lf >= rf),
                else => unreachable,
            };
        }
        return left;
    }

    fn additive(self: *Evaluator) EvalError!Value {
        var left = try self.multiplicative();

        while (self.current_token.tag == .op_plus or self.current_token.tag == .op_minus) {
            const op = self.current_token.tag;
            self.advance();
            const right = try self.multiplicative();

            if (left.tag == .integer and right.tag == .integer) {
                if (op == .op_plus) {
                    left = Value.integer(left.data.int_val + right.data.int_val);
                } else {
                    left = Value.integer(left.data.int_val - right.data.int_val);
                }
            } else {
                const lf = toFloat(left);
                const rf = toFloat(right);
                if (op == .op_plus) {
                    left = Value.float(lf + rf);
                } else {
                    left = Value.float(lf - rf);
                }
            }
        }
        return left;
    }

    fn multiplicative(self: *Evaluator) EvalError!Value {
        var left = try self.primary();

        while (self.current_token.tag == .op_star or self.current_token.tag == .op_slash or self.current_token.tag == .op_percent) {
            const op = self.current_token.tag;
            self.advance();
            const right = try self.primary();

            if (left.tag == .integer and right.tag == .integer) {
                if (op == .op_star) {
                    left = Value.integer(left.data.int_val * right.data.int_val);
                } else if (op == .op_slash) {
                    if (right.data.int_val == 0) return error.DivisionByZero;
                    left = Value.integer(@divTrunc(left.data.int_val, right.data.int_val));
                } else {
                    if (right.data.int_val == 0) return error.DivisionByZero;
                    left = Value.integer(@rem(left.data.int_val, right.data.int_val));
                }
            } else {
                const lf = toFloat(left);
                const rf = toFloat(right);
                if (op == .op_star) {
                    left = Value.float(lf * rf);
                } else if (op == .op_slash) {
                    if (rf == 0.0) return error.DivisionByZero;
                    left = Value.float(lf / rf);
                } else {
                    if (rf == 0.0) return error.DivisionByZero;
                    left = Value.float(@rem(lf, rf));
                }
            }
        }
        return left;
    }

    fn primary(self: *Evaluator) EvalError!Value {
        switch (self.current_token.tag) {
            .number_int => {
                const val = Value.integer(self.current_token.int_val);
                self.advance();
                return val;
            },
            .number_float => {
                const val = Value.float(self.current_token.float_val);
                self.advance();
                return val;
            },
            .string_lit => {
                const val = Value.string(self.current_token.lexeme);
                self.advance();
                return val;
            },
            .kw_true => {
                self.advance();
                return Value.boolean(true);
            },
            .kw_false => {
                self.advance();
                return Value.boolean(false);
            },
            .identifier => {
                const name = self.current_token.lexeme;
                self.advance();
                if (self.getVar(name)) |v| {
                    return v;
                }
                // Undefined variable or syntax error
                return error.SyntaxError;
            },
            .lparen => {
                self.advance();
                const val = try self.expression();
                if (self.current_token.tag != .rparen) return error.SyntaxError;
                self.advance();
                return val;
            },
            .op_minus => {
                self.advance();
                const val = try self.primary();
                if (val.tag == .integer) return Value.integer(-val.data.int_val);
                if (val.tag == .float) return Value.float(-val.data.float_val);
                return error.SyntaxError;
            },
            else => {
                return error.SyntaxError;
            },
        }
    }

    fn formatValue(self: *Evaluator, val: Value) !void {
        switch (val.tag) {
            .none => {},
            .integer => try self.stdout_buf.print(self.allocator, "{d}", .{val.data.int_val}),
            .float => try self.stdout_buf.print(self.allocator, "{d}", .{val.data.float_val}),
            .boolean => try self.stdout_buf.print(self.allocator, "{s}", .{if (val.data.bool_val) "true" else "false"}),
            .string => try self.stdout_buf.print(self.allocator, "{s}", .{val.data.str_val}),
        }
    }
};

fn toFloat(v: Value) f64 {
    return switch (v.tag) {
        .integer => @floatFromInt(v.data.int_val),
        .float => v.data.float_val,
        .boolean => if (v.data.bool_val) 1.0 else 0.0,
        else => 0.0,
    };
}

fn valuesEqual(a: Value, b: Value) bool {
    if (a.tag == .integer and b.tag == .integer) return a.data.int_val == b.data.int_val;
    if (a.tag == .float or b.tag == .float) return toFloat(a) == toFloat(b);
    if (a.tag == .boolean and b.tag == .boolean) return a.data.bool_val == b.data.bool_val;
    if (a.tag == .string and b.tag == .string) return std.mem.eql(u8, a.data.str_val, b.data.str_val);
    return false;
}
