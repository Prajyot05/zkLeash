use alloc::vec::Vec;

pub const MAX_ASSETS: usize = 8;
pub const ONE: u128 = 1_000_000_000_000_000_000;
/// 2.33 in 1e18. `var99 = vol_exposure * Z_VAR99 / ONE`.
pub const Z_VAR99: u128 = 2_330_000_000_000_000_000;
pub const DECISION_DENY: u8 = 0;
pub const DECISION_ALLOW: u8 = 1;
/// `abi.encode` word count of [`crate::encode::encode_public_values`].
pub const PUBLIC_VALUES_WORDS: usize = 52;

#[derive(Clone, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "serde", derive(serde::Serialize, serde::Deserialize))]
pub struct PricePoint {
    pub price: i64,
    pub conf: u64,
    pub expo: i32,
    pub publish_time: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "serde", derive(serde::Serialize, serde::Deserialize))]
pub struct AssetInput {
    pub token: [u8; 20],
    pub decimals: u8,
    pub balance: u128,
    /// Hash chain head immediately before `points[0]`. All zeros if `points[0]` is the first recorded point.
    pub prev_head: [u8; 32],
    pub points: Vec<PricePoint>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "serde", derive(serde::Serialize, serde::Deserialize))]
pub struct Policy {
    pub max_vol_exposure: u128,
    pub max_concentration_bps: u32,
    pub max_drawdown_bps: u32,
    pub max_notional: u128,
    pub max_slippage_bps: u32,
    pub max_window_loss: u128,
    pub window_seconds: u64,
    pub max_trades_per_window: u32,
    pub min_history: u32,
    pub max_price_deviation_bps: u32,
    pub max_price_age: u64,
    pub quote_token: [u8; 20],
    pub quote_index: u8,
}

#[derive(Clone, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "serde", derive(serde::Serialize, serde::Deserialize))]
pub struct LedgerView {
    pub cumulative_pnl: i128,
    pub peak_equity: u128,
    pub window_loss: u128,
    pub window_start: u64,
    pub trades_in_window: u32,
}

#[derive(Clone, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "serde", derive(serde::Serialize, serde::Deserialize))]
pub struct SwapAction {
    pub chain_id: u64,
    pub account: [u8; 20],
    pub router: [u8; 20],
    pub token_in_index: u8,
    pub token_out_index: u8,
    pub fee: u32,
    pub amount_in: u128,
    pub deadline: u64,
    pub nonce: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "serde", derive(serde::Serialize, serde::Deserialize))]
pub struct GuestInput {
    pub policy: Policy,
    pub ledger: LedgerView,
    pub action: SwapAction,
    pub assets: Vec<AssetInput>,
    pub expiry: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PublicValues {
    pub action_hash: [u8; 32],
    pub policy_commitment: [u8; 32],
    pub asset_count: u8,
    pub expiry: u64,
    pub decision: u8,
    pub cumulative_pnl: i128,
    pub peak_equity: u128,
    pub window_loss: u128,
    pub window_start: u64,
    pub trades_in_window: u32,
    pub vol_exposure: u128,
    pub var99: u128,
    pub head_start: [[u8; 32]; MAX_ASSETS],
    pub head_end: [[u8; 32]; MAX_ASSETS],
    pub proven_prices: [i64; MAX_ASSETS],
    pub sigmas: [u128; MAX_ASSETS],
    pub balances: [u128; MAX_ASSETS],
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum DenyReason {
    TooFewAssets,
    TooManyAssets,
    ShortHistory,
    BadPrice,
    Overflow,
    InsufficientBalance,
    VolLimit,
    Concentration,
    Notional,
    Drawdown,
    WindowLoss,
    TradeRate,
    SameToken,
}

impl DenyReason {
    pub fn as_str(&self) -> &'static str {
        match self {
            DenyReason::TooFewAssets => "too_few_assets",
            DenyReason::TooManyAssets => "too_many_assets",
            DenyReason::ShortHistory => "short_history",
            DenyReason::BadPrice => "bad_price",
            DenyReason::Overflow => "overflow",
            DenyReason::InsufficientBalance => "insufficient_balance",
            DenyReason::VolLimit => "vol_limit",
            DenyReason::Concentration => "concentration",
            DenyReason::Notional => "notional",
            DenyReason::Drawdown => "drawdown",
            DenyReason::WindowLoss => "window_loss",
            DenyReason::TradeRate => "trade_rate",
            DenyReason::SameToken => "same_token",
        }
    }
}

#[derive(Clone, Debug)]
pub struct Evaluation {
    pub public_values: PublicValues,
    pub encoded: Vec<u8>,
    pub reasons: Vec<DenyReason>,
    pub step_count: u64,
    pub vol_pre: u128,
    pub equity_pre: u128,
}
