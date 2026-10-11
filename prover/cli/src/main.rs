//! Execute-mode host for the zkLeash risk guest.
//!
//! `leash-risk check --input case.json` runs the guest logic natively (no proof)
//! and prints a one-line JSON object. `--format hex` prints only the abi-encoded
//! public values, which the Foundry tests consume through `vm.ffi`.

use std::env;
use std::fs;
use std::process::ExitCode;

use leash_risk::types::{
    AssetInput, GuestInput, LedgerView, Policy, PricePoint, SwapAction, DECISION_ALLOW,
};
use leash_risk::evaluate;
use serde_json::Value;

fn main() -> ExitCode {
    let mut args = env::args().skip(1);
    let command = args.next().unwrap_or_else(|| "check".to_string());
    if command == "--help" || command == "-h" {
        eprintln!(
            "usage:\n  leash-risk check|execute --input <file> [--format json|hex]\n  leash-risk scenario <calm|volatile_buy|vol_spike_buy|volatile_sell> --account 0x --router 0x --weth 0x --usdc 0x [--amount n] [--now ts] [--nonce n] [--chain-id n] [--max-window-loss n] [--max-vol-exposure n]\n  `check --input` also accepts a JSON array and prints a JSON array"
        );
        return ExitCode::SUCCESS;
    }
    if command == "scenario" {
        return scenario_main(args.collect());
    }
    if command != "check" && command != "execute" {
        eprintln!("unknown command {command}");
        return ExitCode::from(2);
    }
    let mut input_path = None;
    let mut format = "json".to_string();
    let rest: Vec<String> = args.collect();
    let mut i = 0;
    while i < rest.len() {
        match rest[i].as_str() {
            "--input" | "-i" => {
                i += 1;
                input_path = rest.get(i).cloned();
            }
            "--format" | "-f" => {
                i += 1;
                format = rest.get(i).cloned().unwrap_or_else(|| "json".into());
            }
            other => {
                eprintln!("unknown argument {other}");
                return ExitCode::from(2);
            }
        }
        i += 1;
    }
    let path = match input_path {
        Some(p) => p,
        None => {
            eprintln!("missing --input");
            return ExitCode::from(2);
        }
    };
    let raw = match fs::read_to_string(&path) {
        Ok(s) => s,
        Err(err) => {
            eprintln!("failed to read {path}: {err}");
            return ExitCode::from(2);
        }
    };
    let value: Value = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(err) => {
            eprintln!("invalid json: {err}");
            return ExitCode::from(2);
        }
    };
    // An array of inputs is a batch: one JSON array out, exit 0 unless an input is malformed.
    if let Some(items) = value.as_array() {
        let mut outs = Vec::with_capacity(items.len());
        for (idx, item) in items.iter().enumerate() {
            let input = match parse_input(item) {
                Ok(v) => v,
                Err(err) => {
                    eprintln!("invalid input at index {idx}: {err}");
                    return ExitCode::from(2);
                }
            };
            outs.push(evaluation_json(&command, &input, &evaluate(&input)));
        }
        println!("{}", Value::Array(outs));
        return ExitCode::SUCCESS;
    }
    let input = match parse_input(&value) {
        Ok(v) => v,
        Err(err) => {
            eprintln!("invalid input: {err}");
            return ExitCode::from(2);
        }
    };
    let ev = evaluate(&input);
    if format == "hex" {
        println!("0x{}", hex::encode(&ev.encoded));
    } else {
        println!("{}", evaluation_json(&command, &input, &ev));
    }
    if ev.public_values.decision == DECISION_ALLOW {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}

fn evaluation_json(command: &str, input: &GuestInput, ev: &leash_risk::types::Evaluation) -> Value {
    let count = usize::from(ev.public_values.asset_count);
    let reasons: Vec<&str> = ev.reasons.iter().map(|r| r.as_str()).collect();
    let sigmas: Vec<String> = ev.public_values.sigmas[..count].iter().map(|s| s.to_string()).collect();
    let balances: Vec<String> = ev.public_values.balances[..count].iter().map(|b| b.to_string()).collect();
    serde_json::json!({
        "mode": command,
        "decision": ev.public_values.decision,
        "allowed": ev.public_values.decision == DECISION_ALLOW,
        "reasons": reasons,
        "vol_exposure": ev.public_values.vol_exposure.to_string(),
        "vol_pre": ev.vol_pre.to_string(),
        "var99": ev.public_values.var99.to_string(),
        "equity_pre": ev.equity_pre.to_string(),
        "sigmas": sigmas,
        "post_balances": balances,
        "history_points": input.assets.iter().map(|a| a.points.len()).collect::<Vec<_>>(),
        "step_count": ev.step_count,
        "public_values": format!("0x{}", hex::encode(&ev.encoded)),
        "action_hash": format!("0x{}", hex::encode(ev.public_values.action_hash)),
        "policy_commitment": format!("0x{}", hex::encode(ev.public_values.policy_commitment)),
    })
}

fn scenario_main(args: Vec<String>) -> ExitCode {
    let name = match args.first().map(String::as_str) {
        Some("calm") | Some("volatile_buy") | Some("vol_spike_buy") | Some("volatile_sell") => args[0].clone(),
        _ => {
            eprintln!("scenario must be calm, volatile_buy, vol_spike_buy, or volatile_sell");
            return ExitCode::from(2);
        }
    };
    let mut account = None;
    let mut router = None;
    let mut weth = None;
    let mut usdc = None;
    let mut amount: u128 = 100_000_000_000_000_000; // 0.1 WETH
    let mut now: u64 = 1_700_000_000;
    let mut nonce: u64 = 0;
    let mut chain_id: u64 = 31337;
    let mut max_window_loss: Option<u128> = None;
    let mut max_vol_exposure: Option<u128> = None;
    let mut weth_balance: Option<u128> = None;
    let mut usdc_balance: Option<u128> = None;
    let mut window_loss: Option<u128> = None;
    let mut peak_equity: Option<u128> = None;
    let mut trades: Option<u32> = None;
    let mut cumulative_pnl: Option<i128> = None;
    let mut window_start: Option<u64> = None;
    let mut i = 1;
    while i < args.len() {
        let val = args.get(i + 1).cloned();
        match args[i].as_str() {
            "--account" => account = val,
            "--router" => router = val,
            "--weth" => weth = val,
            "--usdc" => usdc = val,
            "--amount" => amount = val.unwrap_or_default().parse().unwrap_or(amount),
            "--now" => now = val.unwrap_or_default().parse().unwrap_or(now),
            "--nonce" => nonce = val.unwrap_or_default().parse().unwrap_or(nonce),
            "--chain-id" => chain_id = val.unwrap_or_default().parse().unwrap_or(chain_id),
            "--max-window-loss" => {
                max_window_loss = val.and_then(|v| v.parse().ok());
            }
            "--max-vol-exposure" => {
                max_vol_exposure = val.and_then(|v| v.parse().ok());
            }
            "--weth-balance" => weth_balance = val.and_then(|v| v.parse().ok()),
            "--usdc-balance" => usdc_balance = val.and_then(|v| v.parse().ok()),
            "--window-loss" => window_loss = val.and_then(|v| v.parse().ok()),
            "--peak-equity" => peak_equity = val.and_then(|v| v.parse().ok()),
            "--trades" => trades = val.and_then(|v| v.parse().ok()),
            "--cumulative-pnl" => cumulative_pnl = val.and_then(|v| v.parse().ok()),
            "--window-start" => window_start = val.and_then(|v| v.parse().ok()),
            other => {
                eprintln!("unknown argument {other}");
                return ExitCode::from(2);
            }
        }
        i += 2;
    }
    let addrs = leash_risk::scenarios::ScenarioAddrs {
        account: match parse_addr_opt(account) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("{e}");
                return ExitCode::from(2);
            }
        },
        router: match parse_addr_opt(router) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("{e}");
                return ExitCode::from(2);
            }
        },
        weth: match parse_addr_opt(weth) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("{e}");
                return ExitCode::from(2);
            }
        },
        usdc: match parse_addr_opt(usdc) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("{e}");
                return ExitCode::from(2);
            }
        },
    };
    let mut scenario = match name.as_str() {
        "calm" => leash_risk::scenarios::calm(addrs, amount, now),
        "vol_spike_buy" => leash_risk::scenarios::vol_spike_buy(addrs, now),
        "volatile_sell" => leash_risk::scenarios::volatile_sell(addrs, now),
        _ => leash_risk::scenarios::volatile_buy(addrs, now),
    };
    scenario.input.action.nonce = nonce;
    scenario.input.action.chain_id = chain_id;
    scenario.input.expiry = now.saturating_add(600);
    scenario.input.action.deadline = now.saturating_add(600);
    if let Some(cap) = max_window_loss {
        scenario.input.policy.max_window_loss = cap;
    }
    if let Some(cap) = max_vol_exposure {
        scenario.input.policy.max_vol_exposure = cap;
    }
    if let Some(bal) = weth_balance {
        scenario.input.assets[0].balance = bal;
    }
    if let Some(bal) = usdc_balance {
        scenario.input.assets[1].balance = bal;
    }
    if let Some(v) = window_loss {
        scenario.input.ledger.window_loss = v;
    }
    if let Some(v) = peak_equity {
        scenario.input.ledger.peak_equity = v;
    }
    if let Some(v) = trades {
        scenario.input.ledger.trades_in_window = v;
    }
    if let Some(v) = cumulative_pnl {
        scenario.input.ledger.cumulative_pnl = v;
    }
    if let Some(v) = window_start {
        scenario.input.ledger.window_start = v;
    }
    scenario.evaluation = evaluate(&scenario.input);
    let ev = &scenario.evaluation;
    let points = |idx: usize| {
        scenario.input.assets[idx]
            .points
            .iter()
            .map(|p| {
                serde_json::json!({
                    "price": p.price,
                    "conf": p.conf,
                    "expo": p.expo,
                    "publish_time": p.publish_time,
                })
            })
            .collect::<Vec<_>>()
    };
    let policy = &scenario.input.policy;
    let out = serde_json::json!({
        "scenario": name,
        "decision": ev.public_values.decision,
        "allowed": ev.public_values.decision == DECISION_ALLOW,
        "reasons": ev.reasons.iter().map(|r| r.as_str()).collect::<Vec<_>>(),
        "public_values": format!("0x{}", hex::encode(&ev.encoded)),
        "action_hash": format!("0x{}", hex::encode(ev.public_values.action_hash)),
        "policy_commitment": format!("0x{}", hex::encode(ev.public_values.policy_commitment)),
        "vol_exposure": ev.public_values.vol_exposure.to_string(),
        "var99": ev.public_values.var99.to_string(),
        "step_count": ev.step_count,
        "fair_out_hint": "computed inside the guest; contract recomputes",
        "amount_in": scenario.input.action.amount_in.to_string(),
        "token_in_index": scenario.input.action.token_in_index,
        "token_out_index": scenario.input.action.token_out_index,
        "fee": scenario.input.action.fee,
        "deadline": scenario.input.action.deadline,
        "nonce": scenario.input.action.nonce,
        "chain_id": scenario.input.action.chain_id,
        "expiry": scenario.input.expiry,
        "policy": {
            "max_vol_exposure": policy.max_vol_exposure.to_string(),
            "max_concentration_bps": policy.max_concentration_bps,
            "max_drawdown_bps": policy.max_drawdown_bps,
            "max_notional": policy.max_notional.to_string(),
            "max_slippage_bps": policy.max_slippage_bps,
            "max_window_loss": policy.max_window_loss.to_string(),
            "window_seconds": policy.window_seconds,
            "max_trades_per_window": policy.max_trades_per_window,
            "min_history": policy.min_history,
            "max_price_deviation_bps": policy.max_price_deviation_bps,
            "max_price_age": policy.max_price_age,
            "quote_index": policy.quote_index,
        },
        "weth_points": points(0),
        "usdc_points": points(1),
        "weth_price": scenario.input.assets[0].points.iter().map(|p| p.price).collect::<Vec<_>>(),
        "weth_conf": scenario.input.assets[0].points.iter().map(|p| p.conf).collect::<Vec<_>>(),
        "weth_time": scenario.input.assets[0].points.iter().map(|p| p.publish_time).collect::<Vec<_>>(),
        "usdc_price": scenario.input.assets[1].points.iter().map(|p| p.price).collect::<Vec<_>>(),
        "usdc_conf": scenario.input.assets[1].points.iter().map(|p| p.conf).collect::<Vec<_>>(),
        "usdc_time": scenario.input.assets[1].points.iter().map(|p| p.publish_time).collect::<Vec<_>>(),
        "expo": -8,
        "weth_balance": scenario.input.assets[0].balance.to_string(),
        "usdc_balance": scenario.input.assets[1].balance.to_string(),
        "post_weth": ev.public_values.balances[0].to_string(),
        "post_usdc": ev.public_values.balances[1].to_string(),
        "sigma_weth": ev.public_values.sigmas[0].to_string(),
        "sigma_usdc": ev.public_values.sigmas[1].to_string(),
    });
    println!("{out}");
    ExitCode::SUCCESS
}

fn parse_addr_opt(value: Option<String>) -> Result<[u8; 20], String> {
    let Some(value) = value else {
        return Err("missing address flag".into());
    };
    parse_addr(&value)
}

fn parse_input(v: &Value) -> Result<GuestInput, String> {
    let policy_v = obj(v, "policy")?;
    let quote = parse_addr(&req_str(policy_v, "quote_token")?)?;
    let policy = Policy {
        max_vol_exposure: parse_u128(req(policy_v, "max_vol_exposure")?)?,
        max_concentration_bps: parse_u32(req(policy_v, "max_concentration_bps")?)?,
        max_drawdown_bps: parse_u32(req(policy_v, "max_drawdown_bps")?)?,
        max_notional: parse_u128(req(policy_v, "max_notional")?)?,
        max_slippage_bps: parse_u32(req(policy_v, "max_slippage_bps")?)?,
        max_window_loss: parse_u128(req(policy_v, "max_window_loss")?)?,
        window_seconds: parse_u64(req(policy_v, "window_seconds")?)?,
        max_trades_per_window: parse_u32(req(policy_v, "max_trades_per_window")?)?,
        min_history: parse_u32(req(policy_v, "min_history")?)?,
        max_price_deviation_bps: parse_u32(req(policy_v, "max_price_deviation_bps")?)?,
        max_price_age: parse_u64(req(policy_v, "max_price_age")?)?,
        quote_token: quote,
        quote_index: parse_u8(req(policy_v, "quote_index")?)?,
    };
    let ledger_v = obj(v, "ledger")?;
    let ledger = LedgerView {
        cumulative_pnl: parse_i128(req(ledger_v, "cumulative_pnl")?)?,
        peak_equity: parse_u128(req(ledger_v, "peak_equity")?)?,
        window_loss: parse_u128(req(ledger_v, "window_loss")?)?,
        window_start: parse_u64(req(ledger_v, "window_start")?)?,
        trades_in_window: parse_u32(req(ledger_v, "trades_in_window")?)?,
    };
    let action_v = obj(v, "action")?;
    let action = SwapAction {
        chain_id: parse_u64(req(action_v, "chain_id")?)?,
        account: parse_addr(&req_str(action_v, "account")?)?,
        router: parse_addr(&req_str(action_v, "router")?)?,
        token_in_index: parse_u8(req(action_v, "token_in_index")?)?,
        token_out_index: parse_u8(req(action_v, "token_out_index")?)?,
        fee: parse_u32(req(action_v, "fee")?)?,
        amount_in: parse_u128(req(action_v, "amount_in")?)?,
        deadline: parse_u64(req(action_v, "deadline")?)?,
        nonce: parse_u64(req(action_v, "nonce")?)?,
    };
    let assets_v = v
        .get("assets")
        .and_then(|a| a.as_array())
        .ok_or("assets must be an array")?;
    let mut assets = Vec::new();
    for asset_v in assets_v {
        let points_v = asset_v
            .get("points")
            .and_then(|p| p.as_array())
            .ok_or("asset.points must be an array")?;
        let mut points = Vec::new();
        for p in points_v {
            points.push(PricePoint {
                price: parse_i64(req(p, "price")?)?,
                conf: parse_u64(req(p, "conf")?)?,
                expo: parse_i32(req(p, "expo")?)?,
                publish_time: parse_u64(req(p, "publish_time")?)?,
            });
        }
        assets.push(AssetInput {
            token: parse_addr(&req_str(asset_v, "token")?)?,
            decimals: parse_u8(req(asset_v, "decimals")?)?,
            balance: parse_u128(req(asset_v, "balance")?)?,
            prev_head: parse_bytes32(&req_str(asset_v, "prev_head")?)?,
            points,
        });
    }
    let expiry = parse_u64(req(v, "expiry")?)?;
    Ok(GuestInput {
        policy,
        ledger,
        action,
        assets,
        expiry,
    })
}

fn obj<'a>(v: &'a Value, key: &str) -> Result<&'a Value, String> {
    v.get(key).filter(|x| x.is_object()).ok_or(format!("{key} must be an object"))
}

fn req<'a>(v: &'a Value, key: &str) -> Result<&'a Value, String> {
    v.get(key).ok_or(format!("missing {key}"))
}

fn req_str(v: &Value, key: &str) -> Result<String, String> {
    req(v, key)?
        .as_str()
        .map(|s| s.to_string())
        .ok_or(format!("{key} must be a string"))
}

fn parse_u128(v: &Value) -> Result<u128, String> {
    match v {
        Value::String(s) => s.parse::<u128>().map_err(|e| e.to_string()),
        Value::Number(n) => n
            .as_u64()
            .map(|x| x as u128)
            .ok_or_else(|| format!("number out of range: {n}")),
        _ => Err("expected number or string".into()),
    }
}

fn parse_i128(v: &Value) -> Result<i128, String> {
    match v {
        Value::String(s) => s.parse::<i128>().map_err(|e| e.to_string()),
        Value::Number(n) => n
            .as_i64()
            .map(|x| x as i128)
            .ok_or_else(|| format!("number out of range: {n}")),
        _ => Err("expected number or string".into()),
    }
}

fn parse_u64(v: &Value) -> Result<u64, String> {
    Ok(parse_u128(v)?.try_into().map_err(|_| "u64 overflow")?)
}

fn parse_u32(v: &Value) -> Result<u32, String> {
    Ok(parse_u128(v)?.try_into().map_err(|_| "u32 overflow")?)
}

fn parse_u8(v: &Value) -> Result<u8, String> {
    Ok(parse_u128(v)?.try_into().map_err(|_| "u8 overflow")?)
}

fn parse_i64(v: &Value) -> Result<i64, String> {
    match v {
        Value::String(s) => s.parse::<i64>().map_err(|e| e.to_string()),
        Value::Number(n) => n.as_i64().ok_or_else(|| format!("bad i64 {n}")),
        _ => Err("expected number or string".into()),
    }
}

fn parse_i32(v: &Value) -> Result<i32, String> {
    Ok(parse_i64(v)?.try_into().map_err(|_| "i32 overflow")?)
}

fn parse_hex(s: &str) -> Result<Vec<u8>, String> {
    let s = s.strip_prefix("0x").unwrap_or(s);
    hex::decode(s).map_err(|e| e.to_string())
}

fn parse_addr(s: &str) -> Result<[u8; 20], String> {
    let bytes = parse_hex(s)?;
    bytes
        .try_into()
        .map_err(|_| "address must be 20 bytes".to_string())
}

fn parse_bytes32(s: &str) -> Result<[u8; 32], String> {
    let bytes = parse_hex(s)?;
    bytes
        .try_into()
        .map_err(|_| "bytes32 must be 32 bytes".to_string())
}
