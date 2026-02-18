# Amazon API Utils

Utility functions for working with Amazon Ads API responses.

## Problem

The Amazon Ads API sometimes returns gzip-compressed responses (identified by magic number `0x1f 0x8b`) instead of plain UTF-8 text, even when the `Content-Encoding` header is not set. This causes `UnicodeDecodeError` when code tries to decode the response directly:

```python
content = data_bytes.decode('utf-8')  # ❌ Fails with gzip data
# UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8b in position 1
```

## Solution

The `decode_api_response()` function automatically handles both plain text and gzip-compressed responses:

```python
from amazon_api_utils import decode_api_response

content = decode_api_response(data_bytes)  # ✅ Works for both plain and gzip
```

## Features

- ✅ **Automatic gzip detection**: Detects gzip magic number (`0x1f 0x8b`)
- ✅ **Transparent decompression**: Automatically decompresses gzip data
- ✅ **Plain text fallback**: Works seamlessly with non-compressed responses
- ✅ **Custom encoding support**: Configurable character encoding (default: UTF-8)
- ✅ **Proper error handling**: Raises appropriate exceptions for invalid data
- ✅ **Debug logging**: Logs compression detection and decompression info

## Usage

### Basic Usage

```python
import requests
from amazon_api_utils import decode_api_response

# Make API request
response = requests.get(api_url, headers=headers)
response.raise_for_status()

# Safely decode response (handles both plain and gzip automatically)
content = decode_api_response(response.content)

# Parse the content
data = json.loads(content)
```

### With Custom Encoding

```python
from amazon_api_utils import decode_api_response

# Decode with custom encoding
content = decode_api_response(data_bytes, encoding='latin-1')
```

### Error Handling

```python
from amazon_api_utils import decode_api_response
import gzip

try:
    content = decode_api_response(data_bytes)
except gzip.BadGzipFile:
    print("Invalid gzip data")
except UnicodeDecodeError:
    print("Invalid UTF-8 data")
```

## API Reference

### `decode_api_response(data_bytes, encoding='utf-8')`

Safely decode API response data, handling both plain text and gzip compression.

**Parameters:**
- `data_bytes` (bytes): Raw bytes from API response
- `encoding` (str, optional): Target encoding. Default: 'utf-8'

**Returns:**
- `str`: Decoded string content

**Raises:**
- `UnicodeDecodeError`: If decompressed data can't be decoded
- `gzip.BadGzipFile`: If gzip header is invalid

## Examples

See `example_fix_unicode_error.py` for detailed examples including:
- Handling plain UTF-8 responses
- Handling gzip-compressed responses
- Integration examples for placement performance sync

Run the example:
```bash
python example_fix_unicode_error.py
```

## Testing

Comprehensive test suite with 17 test cases:

```bash
python test_amazon_api_utils.py
```

**Test Coverage:**
- Plain UTF-8 responses
- Gzip-compressed responses
- Empty responses
- Unicode characters (emoji, non-Latin scripts)
- Large responses (compression verification)
- Edge cases (single byte, two bytes)
- Error conditions (invalid gzip, invalid UTF-8)
- Custom encodings

## Integration

### Fixing amazon_ads_sync.py

If you're encountering the error in `/app/jobs/data_sync/amazon_ads_sync.py` (line 762):

1. Ensure `amazon_api_utils.py` is in your Python path or Docker image
2. Add import at the top of the file:
   ```python
   from amazon_api_utils import decode_api_response
   ```
3. Replace line 762:
   ```python
   # Before:
   content = data_bytes.decode('utf-8')
   
   # After:
   content = decode_api_response(data_bytes)
   ```

### Using in optimizer_core.py

The `optimizer_core.py` file has been updated to use this utility for consistent handling of API responses. See lines 1770-1777 and 1795-1798 for examples.

## Troubleshooting

See `TROUBLESHOOTING.md` for detailed information about:
- Common error messages
- Root causes
- Step-by-step fixes
- Container deployment notes

## License

MIT License - same as the parent project.
