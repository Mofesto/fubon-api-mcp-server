# Python Wheels

此目錄包含私有或第三方 Python wheel 套件。

## fubon_neo

### Windows 版本
- **文件**: `fubon_neo-2.2.8-cp37-abi3-win_amd64.whl`
- **版本**: 2.2.8
- **Python**: 3.7+ (abi3)
- **平台**: Windows AMD64
- **大小**: 2.72 MB

### Linux 版本
- **文件**: `fubon_neo-2.2.8-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`
- **版本**: 2.2.8
- **Python**: 3.7+ (abi3)
- **平台**: Linux x86_64 (manylinux2014)
- **大小**: 4.64 MB

### macOS ARM64 版本 (Apple Silicon)
- **文件**: `fubon_neo-2.2.8-cp37-abi3-macosx_11_0_arm64.whl`
- **版本**: 2.2.8
- **Python**: 3.7+ (abi3)
- **平台**: macOS 11.0+ (ARM64)
- **大小**: 2.65 MB
- **支援**: M1, M2, M3, M4 晶片

### macOS Intel 版本
- **文件**: `fubon_neo-2.2.8-cp37-abi3-macosx_10_12_x86_64.whl`
- **版本**: 2.2.8
- **Python**: 3.7+ (abi3)
- **平台**: macOS 10.12+ (x86_64)
- **大小**: 2.78 MB
- **支援**: Intel 處理器

### 安裝方式

```bash
# 自動選擇平台對應的 wheel (推薦)
pip install -r requirements.txt

# 或手動指定 Windows 版本
pip install wheels/fubon_neo-2.2.8-cp37-abi3-win_amd64.whl

# 或手動指定 Linux 版本
pip install wheels/fubon_neo-2.2.8-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

# 或手動指定 macOS ARM64 版本 (M1/M2/M3/M4)
pip install wheels/fubon_neo-2.2.8-cp37-abi3-macosx_11_0_arm64.whl

# 或手動指定 macOS Intel 版本
pip install wheels/fubon_neo-2.2.8-cp37-abi3-macosx_10_12_x86_64.whl
```

### 支援平台

| 平台 | 架構 | Python | Wheel 文件 | 大小 |
|------|------|--------|------------|------|
| Windows | AMD64 | 3.7+ | fubon_neo-2.2.8-cp37-abi3-win_amd64.whl | 2.72 MB |
| Linux | x86_64 | 3.7+ | fubon_neo-2.2.8-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl | 4.64 MB |
| macOS | ARM64 (M1/M2/M3/M4) | 3.7+ | fubon_neo-2.2.8-cp37-abi3-macosx_11_0_arm64.whl | 2.65 MB |
| macOS | Intel (x86_64) | 3.7+ | fubon_neo-2.2.8-cp37-abi3-macosx_10_12_x86_64.whl | 2.78 MB |

### 注意事項

1. **版權**: fubon_neo 是富邦證券的專有軟體
2. **授權**: 僅供已授權的富邦證券客戶使用
3. **更新**: 新版本需從富邦證券官方網站下載
4. **全平台支援**: Windows, Linux, macOS (Intel & Apple Silicon) 全部支援

### 取得新版本

訪問富邦證券 Trade API 官網：
https://www.fbs.com.tw/TradeAPI/docs/

---

**重要**: 請勿在未經授權的情況下分發此套件
