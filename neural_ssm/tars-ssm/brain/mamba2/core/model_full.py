"""
═══════════════════════════════════════════════════════════════
  TARS HELIX FULL — Complete Model with All Features
═══════════════════════════════════════════════════════════════

Full model integrating ALL GOLDEN spec features:
  - Graduated 8-8-4 layout (SSD → Dual → WKV)
  - MoLE (Mixture of LoRA Experts) every 4 blocks
  - PersonalityAdapter before final output
  - DoubtEngine integration

Architecture:
  Embedding → 20 × HelixBlock (graduated) → PersonalityAdapter → RMSNorm → LM Head

  Blocks 0-7:   SSD ONLY  (fast pattern matching)
  Blocks 8-15:  Dual      (SSD + WKV + WuNeng Fusion)
  Blocks 16-19: WKV ONLY  (deep context tracking)

  MoLE applied after blocks 3, 7, 11, 15, 19 (every 4th block)

Usage:
    from brain.mamba2.core.model_full import TarsHelixFull
    from config import TarsConfig
    cfg = TarsConfig(graduated_layout=True)
    model = TarsHelixFull(cfg)
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import logging
from typing import Optional, Tuple, List
from dataclasses import dataclass

from brain.mamba2.core.ssd import TarsCoreBlock
from brain.mamba2.core.bitnet import RMSNorm, UniversalLinear
from brain.mamba2.routing.mole_router import MoLELayer
from brain.mamba2.adapters.personality_adapter import PersonalityAdapter

logger = logging.getLogger("Tars.HelixFull")


# ═══════════════════════════════════════════
# Graduated layout definition
# ═══════════════════════════════════════════

def get_block_mode(layer_idx: int, n_layers: int = 20, graduated: bool = True) -> str:
    """
    Determine block mode based on GOLDEN spec Graduated 8-8-4 layout.
    
    Blocks 0-7:   SSD only  → fast local patterns
    Blocks 8-15:  Dual      → SSD + WKV fusion (deep understanding)
    Blocks 16-19: WKV only  → long-range context tracking
    
    If graduated=False: all blocks are "dual" (like TarsHelixLite).
    """
    if not graduated:
        return "dual"
    
    # Scale thresholds for different n_layers
    ssd_end = int(n_layers * 0.4)      # 40% → 8 blocks
    dual_end = int(n_layers * 0.8)     # 80% → 16 blocks
    
    if layer_idx < ssd_end:
        return "ssd"
    elif layer_idx < dual_end:
        return "dual"
    else:
        return "wkv"


class HelixBlockFull(nn.Module):
    """
    Full HELIX block with graduated mode + optional MoLE.
    
    RMSNorm → TarsCoreBlock(mode-dependent) → Residual → [MoLE]
    """
    
    def __init__(self, cfg, layer_idx: int = 0, block_mode: str = "dual",
                 use_mole: bool = False):
        super().__init__()
        self.layer_idx = layer_idx
        self.block_mode = block_mode
        self.use_mole = use_mole
        
        self.norm = RMSNorm(cfg.d_model)
        self.core = TarsCoreBlock(
            d_model=cfg.d_model,
            d_state=cfg.d_state,
            d_conv=cfg.d_conv,
            expand=cfg.expand,
            headdim=cfg.headdim,
            ngroups=cfg.ngroups,
            chunk_size=cfg.chunk_size,
            quant_mode=cfg.quant_mode,
            n_meta_tokens=getattr(cfg, 'n_meta_tokens', 8) if block_mode != "wkv" else 0,
            block_mode=block_mode,
        )
        
        # MoLE: applied every N blocks for domain specialization
        if use_mole:
            self.mole = MoLELayer(
                d_model=cfg.d_model,
                n_experts=getattr(cfg, 'n_experts', 8),
                rank=getattr(cfg, 'expert_rank', 8),
                top_k=min(getattr(cfg, 'top_k_experts', 2), getattr(cfg, 'n_experts', 8)),
                quant_mode=cfg.quant_mode,
            )
        else:
            self.mole = None
    
    def forward(
        self,
        x: torch.Tensor,
        wkv_state: Optional[torch.Tensor] = None,
        x_prev: Optional[torch.Tensor] = None,
        ssd_state: Optional[torch.Tensor] = None,
        conv_state: Optional[torch.Tensor] = None,
    ):
        """
        x: [B, L, d_model]
        Returns: (x_out, wkv_state, x_last, ssd_state, conv_state, aux_loss)
        """
        residual = x
        h = self.norm(x)
        out, wkv_state, x_last, ssd_state, conv_state = self.core(
            h, wkv_state, x_prev, ssd_state, conv_state
        )
        x = residual + out
        
        # MoLE: domain specialization
        aux_loss = torch.tensor(0.0, device=x.device)
        if self.mole is not None:
            x, aux = self.mole(x)
            aux_loss = aux
        
        return x, wkv_state, x_last, ssd_state, conv_state, aux_loss


class TarsHelixFull(nn.Module):
    """
    TARS HELIX FULL — Complete 380M model with all features.
    
    Architecture:
      Embedding(48256, 1024) → 20 × HelixBlockFull → PersonalityAdapter → RMSNorm → LM Head
    
    Features:
      ✅ Graduated 8-8-4 layout (SSD → Dual → WKV)
      ✅ MoLE (8 LoRA experts, top-2 routing) every 4 blocks
      ✅ PersonalityAdapter (iterative convergence-gated)
      ✅ Weight-tied LM Head
      ✅ Gradient checkpointing support
      ✅ Stateful generation with per-block state
    """
    
    def __init__(self, cfg=None):
        super().__init__()
        if cfg is None:
            from config import TarsConfig
            cfg = TarsConfig()
        
        self.cfg = cfg
        self.d_model = cfg.d_model
        self.n_layers = cfg.n_layers
        self.vocab_size = cfg.vocab_size
        graduated = getattr(cfg, 'graduated_layout', True)
        mole_every_n = getattr(cfg, 'mole_every_n', 4)
        
        # ═══ Embedding (weight-tied with LM head) ═══
        self.embedding = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.embed_scale = math.sqrt(cfg.d_model)  # Vaswani scaling
        
        # ═══ 20 HelixBlocks with graduated layout + MoLE ═══
        self.blocks = nn.ModuleList()
        layout_summary = []
        for i in range(cfg.n_layers):
            mode = get_block_mode(i, cfg.n_layers, graduated)
            use_mole = ((i + 1) % mole_every_n == 0)  # Every 4th block
            self.blocks.append(HelixBlockFull(
                cfg, layer_idx=i, block_mode=mode, use_mole=use_mole,
            ))
            mole_mark = "+MoLE" if use_mole else ""
            layout_summary.append(f"  Block {i:2d}: {mode:4s} {mole_mark}")
        
        # ═══ PersonalityAdapter ═══
        style_dim = getattr(cfg, 'personality_style_dim', 128)
        max_passes = getattr(cfg, 'personality_max_passes', 3)
        self.personality = PersonalityAdapter(
            d_model=cfg.d_model,
            style_dim=style_dim,
            max_passes=max_passes,
        )
        
        # ═══ Final RMSNorm ═══
        self.final_norm = RMSNorm(cfg.d_model)
        
        # ═══ LM Head (weight-tied) ═══
        self.lm_head = nn.Linear(cfg.vocab_size, cfg.d_model, bias=False)
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        self.lm_head.weight = self.embedding.weight
        
        # Initialize weights
        self._init_weights()
        
        # Log architecture
        n_params = sum(p.numel() for p in self.parameters())
        n_trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        logger.info(
            f"TarsHelixFull: {n_params/1e6:.1f}M params "
            f"({n_trainable/1e6:.1f}M trainable), "
            f"d={cfg.d_model}, L={cfg.n_layers}, V={cfg.vocab_size}"
        )
        logger.info(f"Layout ({'graduated' if graduated else 'uniform'}):")
        for line in layout_summary:
            logger.info(line)
        logger.info(f"PersonalityAdapter: style_dim={style_dim}, max_passes={max_passes}")
        logger.info(f"MoLE: every {mole_every_n} blocks, "
                     f"{getattr(cfg, 'n_experts', 8)} experts × rank={getattr(cfg, 'expert_rank', 8)}")
    
    def _init_weights(self):
        """Initialize weights with scaled initialization."""
        for name, p in self.named_parameters():
            if p.dim() >= 2:
                nn.init.normal_(p, mean=0.0, std=0.02)
            elif 'bias' in name:
                nn.init.zeros_(p)
    
    def forward(
        self,
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        return_hidden: bool = False,
    ) -> dict:
        """
        Training forward pass.
        
        Returns:
            dict with:
              'logits': [B, L, V]
              'loss': scalar (if labels provided, includes MoLE aux loss)
              'hidden': [B, L, d_model] (if return_hidden)
              'aux_loss': scalar (MoLE auxiliary loss)
        """
        B, L = input_ids.shape
        
        # 1. Embed + scale
        x = self.embedding(input_ids) * self.embed_scale
        
        # 2. Sequential block processing with gradient checkpointing
        use_ckpt = getattr(self, '_use_gradient_checkpointing', False) and self.training
        total_aux_loss = torch.tensor(0.0, device=x.device)
        
        for block in self.blocks:
            if use_ckpt:
                def create_custom_forward(module):
                    def custom_forward(hidden_states):
                        orig_dtype = hidden_states.dtype
                        with torch.amp.autocast('cuda', enabled=False):
                            out = module(hidden_states.float())
                        return out[0].to(orig_dtype), out[5]  # x, aux_loss
                    return custom_forward
                
                if not x.requires_grad:
                    x.requires_grad_(True)
                
                x, aux = torch.utils.checkpoint.checkpoint(
                    create_custom_forward(block),
                    x,
                    use_reentrant=False,
                )
                total_aux_loss = total_aux_loss + aux
            else:
                x, _, _, _, _, aux = block(x)
                total_aux_loss = total_aux_loss + aux
        
        # 3. PersonalityAdapter (style transform)
        x = self.personality(x)
        
        # 4. Final norm
        x = self.final_norm(x)
        
        # 5. LM Head
        logits = self.lm_head(x)
        
        # 6. Loss
        result = {'logits': logits, 'aux_loss': total_aux_loss}
        
        if labels is not None:
            # Labels are ALREADY shifted by the dataset
            lm_loss = F.cross_entropy(
                logits.view(-1, self.vocab_size),
                labels.view(-1),
                ignore_index=-100,
            )
            # Total loss = LM + MoLE auxiliary
            result['loss'] = lm_loss + total_aux_loss
            result['lm_loss'] = lm_loss
        
        if return_hidden:
            result['hidden'] = x
        
        return result
    
    @torch.no_grad()
    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 256,
        temperature: float = 0.8,
        top_p: float = 0.95,
        top_k: int = 50,
    ) -> torch.Tensor:
        """
        Autoregressive generation with full state management.
        Each block maintains its own (wkv_state, x_prev, ssd_state, conv_state).
        """
        self.eval()
        generated = input_ids.clone()
        
        # Initialize states per block
        states = [{
            'wkv_state': None,
            'x_prev': None,
            'ssd_state': None,
            'conv_state': None,
        } for _ in range(self.n_layers)]
        
        # Prefill: process entire prompt
        x = self.embedding(input_ids) * self.embed_scale
        for i, block in enumerate(self.blocks):
            x, wkv, x_last, ssd, conv, _ = block(x, **states[i])
            states[i] = {
                'wkv_state': wkv,
                'x_prev': x_last,
                'ssd_state': ssd,
                'conv_state': conv,
            }
        
        x = self.personality(x)
        h = self.final_norm(x)
        logits = self.lm_head(h[:, -1:, :])
        
        for step in range(max_new_tokens):
            # Sample
            next_logits = logits[:, -1, :] / max(temperature, 1e-5)
            
            # Top-k filtering
            if top_k > 0:
                v, _ = torch.topk(next_logits, min(top_k, next_logits.size(-1)))
                next_logits[next_logits < v[:, [-1]]] = float('-inf')
            
            # Top-p (nucleus) filtering
            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
                cum_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                mask = cum_probs - F.softmax(sorted_logits, dim=-1) >= top_p
                sorted_logits[mask] = float('-inf')
                next_logits = sorted_logits.scatter(1, sorted_indices, sorted_logits)
            
            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            generated = torch.cat([generated, next_token], dim=1)
            
            # Forward one token through all blocks (step mode)
            x = self.embedding(next_token) * self.embed_scale
            for i, block in enumerate(self.blocks):
                x, wkv, x_last, ssd, conv, _ = block(x, **states[i])
                states[i] = {
                    'wkv_state': wkv,
                    'x_prev': x_last,
                    'ssd_state': ssd,
                    'conv_state': conv,
                }
            
            x = self.personality(x)
            h = self.final_norm(x)
            logits = self.lm_head(h)
            
            # Check for EOS
            if next_token.shape[0] == 1 and next_token.item() == 0:
                break
        
        return generated
    
    def count_parameters(self) -> dict:
        """Count parameters by component."""
        counts = {}
        total = 0
        for name, p in self.named_parameters():
            parts = name.split('.')
            component = parts[0]
            if component == 'blocks' and len(parts) > 2:
                block_idx = int(parts[1])
                sub = parts[2]
                component = f"blocks.{block_idx}.{sub}"
            if component not in counts:
                counts[component] = 0
            counts[component] += p.numel()
            total += p.numel()
        
        # Summary by type
        ssd_params = sum(v for k, v in counts.items() if 'core' in k and 
                         any(f'blocks.{i}.' in k for i in range(8)))
        dual_params = sum(v for k, v in counts.items() if 'core' in k and 
                          any(f'blocks.{i}.' in k for i in range(8, 16)))
        wkv_params = sum(v for k, v in counts.items() if 'core' in k and 
                         any(f'blocks.{i}.' in k for i in range(16, 20)))
        mole_params = sum(v for k, v in counts.items() if 'mole' in k)
        personality_params = sum(v for k, v in counts.items() if 'personality' in k)
        
        counts['_summary'] = {
            'ssd_blocks': ssd_params,
            'dual_blocks': dual_params,
            'wkv_blocks': wkv_params,
            'mole_total': mole_params,
            'personality': personality_params,
            'total': total,
            'total_M': total / 1e6,
        }
        return counts
