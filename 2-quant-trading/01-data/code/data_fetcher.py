#!/usr/bin/env python3
"""
数据获取模块 - 使用 akshare 获取 A 股和 ETF 数据

数据源策略（简单优先）：
  1. 本地 parquet 缓存（最快）
  2. 新浪源（主力线上源，支持 qfq / 手动拆股检测）
  3. 腾讯源（容灾回退，不支持复权）
  
  ❌ 不再使用东方财富（fund_etf_hist_em / stock_zh_a_hist）
  
各标的类型对应：
  ETF → fund_etf_hist_sina（新浪，手动拆股）
  A 股 → stock_zh_a_daily（新浪，原生 qfq）
  回退 → stock_zh_index_daily_tx（腾讯，无复权）
"""

import akshare as ak
import pandas as pd
import os
from datetime import datetime
from typing import Optional

# ── 缓存目录（模块级，首次自动创建） ──
DATA_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def _detect_and_adjust(df: pd.DataFrame) -> pd.DataFrame:
    """
    检测拆股/送股并前复权（新浪源用）。
    
    逻辑：单日价格变化 > ±50% 视为拆股事件，
    将该事件之前的所有价格按比例调低。
    """
    pct = df['close'].pct_change()
    split_idx = pct[pct.abs() > 0.5].index
    if not split_idx.empty:
        idx = split_idx[0]
        factor = df.loc[idx, 'close'] / df.loc[idx - 1, 'close']
        print(f"    检测到拆股: {df.loc[idx, 'date'].date()}, 因子={factor:.4f}")
        for col in ['open', 'high', 'low', 'close']:
            df.loc[df.index < idx, col] *= factor
    return df


def _cache_path(symbol: str) -> str:
    return os.path.join(DATA_CACHE_DIR, f"{symbol}.parquet")


def _read_cache(symbol: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    path = _cache_path(symbol)
    if not os.path.exists(path):
        return None
    try:
        df = load_data(path)
    except Exception:
        return None
    s = pd.to_datetime(start_date)
    e = pd.to_datetime(end_date)
    clipped = df[(df.index >= s) & (df.index <= e)]
    if len(clipped) > 0:
        print(f"  [缓存] 命中 {symbol} ({len(clipped)} 条, {start_date}~{end_date})")
        return clipped
    return None


def fetch_etf_data(
    symbol: str = "510300",
    start_date: str = "20210101",
    end_date: Optional[str] = None,
    save_path: Optional[str] = None
) -> pd.DataFrame:
    """
    获取 ETF 日线数据。

    数据源优先级：
      1. 本地 parquet 缓存
      2. 新浪 fund_etf_hist_sina（主力，手动拆股检测）
      3. 腾讯 stock_zh_index_daily_tx（容灾回退，无复权）

    Args:
        symbol: ETF 代码，如 "510300" (沪深300ETF)
        start_date: 开始日期，格式 YYYYMMDD
        end_date: 结束日期，格式 YYYYMMDD，默认为今天
        save_path: 保存路径，None 则不保存

    Returns:
        DataFrame，索引为 DatetimeIndex，列含 Open/High/Low/Close/Volume
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")

    cached = _read_cache(symbol, start_date, end_date)
    if cached is not None:
        return cached

    print(f"获取 ETF {symbol} 数据: {start_date} ~ {end_date}")

    # --- ① 新浪源（主力，需手动拆股检测） ---
    try:
        prefix = "sh" if symbol.startswith(("5", "6")) else "sz"
        df = ak.fund_etf_hist_sina(symbol=f"{prefix}{symbol}")
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        df = _detect_and_adjust(df)

        s = pd.to_datetime(start_date)
        e = pd.to_datetime(end_date)
        df = df[(df['date'] >= s) & (df['date'] <= e)].set_index('date')
        df.index.name = 'Date'
        df = df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low',
            'close': 'Close', 'volume': 'Volume',
        })
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        print(f"  [新浪源] 获取完成，共 {len(df)} 条记录")
        _save(df, symbol, save_path)
        _save(df, symbol, _cache_path(symbol))
        return df
    except Exception as e:
        print(f"  [新浪源] 不可用 ({type(e).__name__})，回退到腾讯源")

    # --- ② 腾讯源（容灾回退，无复权） ---
    try:
        prefix = "sh" if symbol.startswith(("5", "6")) else "sz"
        df = ak.stock_zh_index_daily_tx(
            symbol=f"{prefix}{symbol}",
            start_date=start_date,
            end_date=end_date,
        )
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        df.index.name = 'Date'
        df = df.rename(columns={
            'open': 'Open', 'close': 'Close',
            'high': 'High', 'low': 'Low', 'amount': 'Volume',
        })
        df['Volume'] = df['Volume'] * 100  # 手 → 股
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        print(f"  [腾讯源] 获取完成，共 {len(df)} 条记录")
        _save(df, symbol, save_path)
        _save(df, symbol, _cache_path(symbol))
        return df
    except Exception as e:
        raise RuntimeError(f"所有数据源不可用: {type(e).__name__}") from e


def fetch_stock_data(
    symbol: str = "600519",
    start_date: str = "20210101",
    end_date: Optional[str] = None,
    adjust: str = "qfq",
    save_path: Optional[str] = None
) -> pd.DataFrame:
    """
    获取 A 股日线数据。

    数据源优先级：
      1. 本地 parquet 缓存
      2. 新浪 stock_zh_a_daily（主力，原生 qfq 复权）
      3. 腾讯 stock_zh_index_daily_tx（容灾回退，无复权）

    Args:
        symbol: 股票代码，如 "600519" (贵州茅台)
        start_date: 开始日期，格式 YYYYMMDD
        end_date: 结束日期，格式 YYYYMMDD，默认为今天
        adjust: 复权方式，"qfq" 前复权，"" 不复权（仅新浪源生效）
        save_path: 保存路径，None 则不保存

    Returns:
        DataFrame，索引为 DatetimeIndex，列含 Open/High/Low/Close/Volume
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")

    cached = _read_cache(symbol, start_date, end_date)
    if cached is not None:
        return cached

    print(f"获取股票 {symbol} 数据: {start_date} ~ {end_date}")

    # --- ① 新浪源（主力，支持原生 qfq 复权） ---
    try:
        prefix = "sh" if symbol.startswith(("6", "9")) else "sz"
        df = ak.stock_zh_a_daily(
            symbol=f"{prefix}{symbol}",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        df.index.name = 'Date'
        df = df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low',
            'close': 'Close', 'volume': 'Volume',
        })
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        print(f"  [新浪源] 获取完成，共 {len(df)} 条记录")
        _save(df, symbol, save_path)
        _save(df, symbol, _cache_path(symbol))
        return df
    except Exception as e:
        print(f"  [新浪源] 不可用 ({type(e).__name__})，回退到腾讯源")

    # --- ② 腾讯源（容灾回退，无复权） ---
    try:
        prefix = "sh" if symbol.startswith(("6", "9")) else "sz"
        df = ak.stock_zh_index_daily_tx(
            symbol=f"{prefix}{symbol}",
            start_date=start_date,
            end_date=end_date,
        )
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        df.index.name = 'Date'
        df = df.rename(columns={
            'open': 'Open', 'close': 'Close',
            'high': 'High', 'low': 'Low', 'amount': 'Volume',
        })
        df['Volume'] = df['Volume'] * 100  # 手 → 股
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        print(f"  [腾讯源] 获取完成，共 {len(df)} 条记录")
        _save(df, symbol, save_path)
        _save(df, symbol, _cache_path(symbol))
        return df
    except Exception as e:
        raise RuntimeError(f"所有数据源不可用: {type(e).__name__}") from e


def _save(df: pd.DataFrame, symbol: str, save_path: Optional[str]) -> None:
    if not save_path:
        return
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    if save_path.endswith('.csv'):
        df.to_csv(save_path)
    else:
        path = save_path if save_path.endswith('.parquet') else f"{save_path}.parquet"
        df.to_parquet(path)
    print(f"  数据已保存到: {path}")


def fetch_multiple_symbols(
    symbols: list[str],
    start_date: str = "20210101",
    end_date: Optional[str] = None,
    adjust: str = "qfq",
    output_dir: str = "./data"
) -> dict[str, pd.DataFrame]:
    """批量获取多个标的的数据，自动判断 ETF 还是 A 股。"""
    data_dict = {}
    for symbol in symbols:
        try:
            save_path = os.path.join(output_dir, f"{symbol}.parquet")
            if symbol.startswith(("5", "1")):
                df = fetch_etf_data(symbol, start_date, end_date, save_path)
            else:
                df = fetch_stock_data(symbol, start_date, end_date, adjust, save_path)
            data_dict[symbol] = df
        except Exception as e:
            print(f"获取 {symbol} 失败: {e}")
    return data_dict


def load_data(file_path: str) -> pd.DataFrame:
    """从 .parquet 或 .csv 文件加载数据，确保列名和索引格式统一。"""
    if file_path.endswith('.parquet'):
        df = pd.read_parquet(file_path)
    elif file_path.endswith('.csv'):
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    else:
        raise ValueError(f"不支持的文件格式: {file_path}")
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df.index.name = 'Date'
    df.columns = [c.capitalize() for c in df.columns]
    return df


# 常用标的代码
SYMBOLS = {
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "159915": "创业板ETF",
    "512100": "中证1000ETF",
    "600519": "贵州茅台",
    "000858": "五粮液",
    "601318": "中国平安",
    "000001": "平安银行",
    "600036": "招商银行",
}

if __name__ == "__main__":
    df = fetch_etf_data(symbol="510300", start_date="20210101")
    print("\n数据预览:")
    print(df.head())
    print(f"\n数据形状: {df.shape}")
    print(f"时间范围: {df.index[0]} ~ {df.index[-1]}")
