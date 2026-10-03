use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int, c_uint};

pub type Z3Config = *mut std::ffi::c_void;
pub type Z3Context = *mut std::ffi::c_void;
pub type Z3Solver = *mut std::ffi::c_void;
pub type Z3Ast = *mut std::ffi::c_void;
pub type Z3Model = *mut std::ffi::c_void;
pub type Z3AstVector = *mut std::ffi::c_void;
pub type Z3Symbol = *mut std::ffi::c_void;
pub type Z3Sort = *mut std::ffi::c_void;
pub type Z3FuncDecl = *mut std::ffi::c_void;

pub const Z3_L_FALSE: c_int = -1; // UNSAT
pub const Z3_L_UNDEF: c_int = 0;  // UNKNOWN
pub const Z3_L_TRUE: c_int = 1;   // SAT

extern "C" {
    pub fn Z3_mk_config() -> Z3Config;
    pub fn Z3_del_config(c: Z3Config);
    pub fn Z3_mk_context(c: Z3Config) -> Z3Context;
    pub fn Z3_del_context(c: Z3Context);

    pub fn Z3_mk_solver(c: Z3Context) -> Z3Solver;
    pub fn Z3_solver_inc_ref(c: Z3Context, s: Z3Solver);
    pub fn Z3_solver_dec_ref(c: Z3Context, s: Z3Solver);
    pub fn Z3_solver_assert(c: Z3Context, s: Z3Solver, a: Z3Ast);
    pub fn Z3_solver_check(c: Z3Context, s: Z3Solver) -> c_int;

    pub fn Z3_solver_get_model(c: Z3Context, s: Z3Solver) -> Z3Model;
    pub fn Z3_model_inc_ref(c: Z3Context, m: Z3Model);
    pub fn Z3_model_dec_ref(c: Z3Context, m: Z3Model);
    pub fn Z3_model_to_string(c: Z3Context, m: Z3Model) -> *const c_char;

    pub fn Z3_eval_smtlib2_string(c: Z3Context, str: *const c_char) -> *const c_char;

    pub fn Z3_parse_smtlib2_string(
        c: Z3Context,
        str: *const c_char,
        num_sorts: c_uint,
        sort_names: *const Z3Symbol,
        sorts: *const Z3Sort,
        num_decls: c_uint,
        decl_names: *const Z3Symbol,
        decls: *const Z3FuncDecl,
    ) -> Z3AstVector;

    pub fn Z3_ast_vector_inc_ref(c: Z3Context, v: Z3AstVector);
    pub fn Z3_ast_vector_dec_ref(c: Z3Context, v: Z3AstVector);
    pub fn Z3_ast_vector_size(c: Z3Context, v: Z3AstVector) -> c_uint;
    pub fn Z3_ast_vector_get(c: Z3Context, v: Z3AstVector, i: c_uint) -> Z3Ast;
}

pub struct SafeZ3Context {
    pub ctx: Z3Context,
}

impl SafeZ3Context {
    pub fn new() -> Option<Self> {
        unsafe {
            let cfg = Z3_mk_config();
            if cfg.is_null() {
                return None;
            }
            let ctx = Z3_mk_context(cfg);
            Z3_del_config(cfg);
            if ctx.is_null() {
                None
            } else {
                Some(Self { ctx })
            }
        }
    }
}

impl Drop for SafeZ3Context {
    fn drop(&mut self) {
        unsafe {
            if !self.ctx.is_null() {
                Z3_del_context(self.ctx);
                self.ctx = std::ptr::null_mut();
            }
        }
    }
}

pub struct SafeZ3Solver<'a> {
    pub ctx: &'a SafeZ3Context,
    pub solver: Z3Solver,
}

impl<'a> SafeZ3Solver<'a> {
    pub fn new(ctx: &'a SafeZ3Context) -> Option<Self> {
        unsafe {
            let s = Z3_mk_solver(ctx.ctx);
            if s.is_null() {
                return None;
            }
            Z3_solver_inc_ref(ctx.ctx, s);
            Some(Self { ctx, solver: s })
        }
    }

    pub fn assert_formula(&self, ast: Z3Ast) {
        unsafe {
            Z3_solver_assert(self.ctx.ctx, self.solver, ast);
        }
    }

    pub fn assert_smtlib2(&self, smt_script: &str) -> bool {
        let c_str = match CString::new(smt_script) {
            Ok(s) => s,
            Err(_) => return false,
        };
        unsafe {
            let vec = Z3_parse_smtlib2_string(
                self.ctx.ctx,
                c_str.as_ptr(),
                0,
                std::ptr::null(),
                std::ptr::null(),
                0,
                std::ptr::null(),
                std::ptr::null(),
            );
            if vec.is_null() {
                return false;
            }
            Z3_ast_vector_inc_ref(self.ctx.ctx, vec);
            let size = Z3_ast_vector_size(self.ctx.ctx, vec);
            for i in 0..size {
                let ast = Z3_ast_vector_get(self.ctx.ctx, vec, i);
                Z3_solver_assert(self.ctx.ctx, self.solver, ast);
            }
            Z3_ast_vector_dec_ref(self.ctx.ctx, vec);
            true
        }
    }

    pub fn check(&self) -> (c_int, Option<String>) {
        unsafe {
            let res = Z3_solver_check(self.ctx.ctx, self.solver);
            let model_str = if res == Z3_L_TRUE {
                let m = Z3_solver_get_model(self.ctx.ctx, self.solver);
                if !m.is_null() {
                    Z3_model_inc_ref(self.ctx.ctx, m);
                    let ptr = Z3_model_to_string(self.ctx.ctx, m);
                    let s = if !ptr.is_null() {
                        CStr::from_ptr(ptr).to_string_lossy().to_string()
                    } else {
                        String::new()
                    };
                    Z3_model_dec_ref(self.ctx.ctx, m);
                    Some(s)
                } else {
                    None
                }
            } else {
                None
            };
            (res, model_str)
        }
    }
}

impl<'a> Drop for SafeZ3Solver<'a> {
    fn drop(&mut self) {
        unsafe {
            if !self.solver.is_null() {
                Z3_solver_dec_ref(self.ctx.ctx, self.solver);
                self.solver = std::ptr::null_mut();
            }
        }
    }
}
