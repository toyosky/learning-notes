#!/usr/bin/env python3
"""
数据获取模块 - 使用 akshare 获取 A 股和 ETF 数据
基于 2.1-data-akshare.md 笔记
"""

import akshare as ak
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Optional


def fetch_etf_data(
    symbol: str = "510300",
    start_date: str = "20210101",
    end_date: Optional[str] = None,
    adjust: str = "qfq",
    save_path: Optional[str] = None
) -> pd.DataFrame:
    """
    获取 ETF 日线数据
    
    Args:
        symbol: ETF 代码，如 "510300" (沪深300ETF)
        start_date: 开始日期，格式 YYYYMMDD
        end_date: 结束日期，格式 YYYYMMDD，默认为今天
        adjust: 复权方式，"qfq" 前复权，"" 不复权
        save_path: 保存路径，None 则不保存
    
    Returns:
        DataFrame，索引为 DatetimeIndex，列含 Open/High/Low/Close/Volume
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    
    print(f"获取 ETF {symbol} 数据: {start_date} ~ {end_date}")
    
    # 获取数据
    df = ak.fund_etf_hist_em(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust=adjust
    )
    
    # 日期列 → DatetimeIndex
    df['日期'] = pd.to_datetime(df['日期'])
    df = df.set_index('日期')
    df.index.name = 'Date'
    
    # 重命名关键列
    df = df.rename(columns={
        '开盘': 'Open',
        '收盘': 'Close',
        '最高': 'High',
        '最低': 'Low',
        '成交量': 'Volume',
    })
    
    # 只保留关键列
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    
    print(f"获取完成，共 {len(df)} 条记录")
    
    # 保存到文件
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        if save_path.endswith('.parquet'):
            df.to_parquet(save_path)
        elif save_path.endswith('.csv'):
            df.to_csv(save_path)
        else:
            # 默认保存为 parquet
            save_path = save_path + '.parquet'
            df.to_parquet(save_path)
        print(f"数据已保存到: {save_path}")
    
    return df


def fetch_stock_data(
    symbol: str = "600519",
    start_date: str = "20210101",
    end_date: Optional[str] = None,
    adjust: str = "qfq",
    save_path: Optional[str] = None
) -> pd.DataFrame:
    """
    获取 A 股日线数据
    
    Args:
        symbol: 股票代码，如 "600519" (贵州茅台)
        start_date: 开始日期，格式 YYYYMMDD
        end_date: 结束日期，格式 YYYYMMDD，默认为今天
        adjust: 复权方式，"qfq" 前复权，"" 不复权
        save_path: 保存路径，None 则不保存
    
    Returns:
        DataFrame，索引为 DatetimeIndex，列含 Open/High/Low/Close/Volume
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    
    print(f"获取股票 {symbol} 数据: {start_date} ~ {end_date}")
    
    # 获取数据
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust=adjust
    )
    
    # 日期列 → DatetimeIndex
    df['日期'] = pd.to_datetime(df['日期'])
    df = df.set_index('日期')
    df.index.name = 'Date'
    
    # 重命名关键列
    df = df.rename(columns={
        '开盘': 'Open',
        '收盘': 'Close',
        '最高': 'High',
        '最低': 'Low',
        '成交量': 'Volume',
    })
    
    # 只保留关键列
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    
    print(f"获取完成，共 {len(df)} 条记录")
    
    # 保存到文件
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        if save_path.endswith('.parquet'):
            df.to_parquet(save_path)
        elif save_path.endswith('.csv'):
            df.to_csv(save_path)
        else:
            save_path = save_path + '.parquet'
            df.to_parquet(save_path)
        print(f"数据已保存到: {save_path}")
    
    return df


def fetch_multiple_symbols(
    symbols: list[str],
    start_date: str = "20210101",
    end_date: Optional[str] = None,
    adjust: str = "qfq",
    output_dir: str = "./data"
) -> dict[str, pd.DataFrame]:
    """
    批量获取多个标的的数据
    
    Args:
        symbols: 标的代码列表，如 ["510300", "600519", "000858"]
        start_date: 开始日期
        end_date: 结束日期
        adjust: 复权方式
        output_dir: 输出目录
    
    Returns:
        字典，key 为标的代码，value 为 DataFrame
    """
    data_dict = {}
    
    for symbol in symbols:
        try:
            save_path = os.path.join(output_dir, f"{symbol}.parquet")
            
            # 判断是 ETF 还是股票
            if symbol.startswith("5") or symbol.startswith("1"):
                # ETF
                df = fetch_etf_data(symbol, start_date, end_date, adjust, save_path)
            else:
                # A 股
                df = fetch_stock_data(symbol, start_date, end_date, adjust, save_path)
            
            data_dict[symbol] = df
            
        except Exception as e:
            print(f"获取 {symbol} 失败: {e}")
    
    return data_dict


def load_data(file_path: str) -> pd.DataFrame:
    """
    从文件加载数据
    
    Args:
        file_path: 文件路径，支持 .parquet 和 .csv
    
    Returns:
        DataFrame
    """
    if file_path.endswith('.parquet'):
        df = pd.read_parquet(file_path)
    elif file_path.endswith('.csv'):
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    else:
        raise ValueError(f"不支持的文件格式: {file_path}")
    
    # 确保索引是 DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    df.index.name = 'Date'
    
    # 确保列名首字母大写
    df.columns = [c.capitalize() for c in df.columns]
    
    return df


# 常用标的代码
SYMBOLS = {
    # ETF
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "159915": "创业板ETF",
    "512100": "中证1000ETF",
    
    # A 股
    "600519": "贵州茅台",
    "000858": "五粮液",
    "601318": "中国平安",
    "000001": "平安银行",
    "600036": "招商银行",
}


if __name__ == "__main__":
    # 示例：获取沪深300ETF数据
    df = fetch_etf_data(
        symbol="510300",
        start_date="20210101",
        save_path="./data/510300.parquet"
    )
    
    print("\n数据预览:")
    print(df.head())
    print(f"\n数据形状: {df.shape}")
    print(f"时间范围: {df.index[0]} ~ {df.index[-1]}")
