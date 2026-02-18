#!/usr/bin/env python3
"""
Tests for amazon_api_utils module

Tests the decode_api_response function with various inputs:
- Plain UTF-8 text
- Gzip-compressed data
- Empty responses
- Invalid gzip data
- Different encodings
"""

import gzip
import logging
import unittest

from amazon_api_utils import decode_api_response

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)


class TestDecodeAPIResponse(unittest.TestCase):
    """Test cases for decode_api_response function"""
    
    def test_plain_text_response(self):
        """Test decoding plain UTF-8 text"""
        test_string = "Hello, World!"
        data_bytes = test_string.encode('utf-8')
        
        result = decode_api_response(data_bytes)
        
        self.assertEqual(result, test_string)
        self.assertIsInstance(result, str)
    
    def test_gzip_compressed_response(self):
        """Test decoding gzip-compressed data"""
        test_string = "This is a gzip-compressed response from Amazon Ads API"
        compressed = gzip.compress(test_string.encode('utf-8'))
        
        # Verify it has the gzip magic number
        self.assertEqual(compressed[0], 0x1f)
        self.assertEqual(compressed[1], 0x8b)
        
        result = decode_api_response(compressed)
        
        self.assertEqual(result, test_string)
        self.assertIsInstance(result, str)
    
    def test_empty_plain_response(self):
        """Test decoding empty plain text response"""
        data_bytes = b""
        
        result = decode_api_response(data_bytes)
        
        self.assertEqual(result, "")
        self.assertIsInstance(result, str)
    
    def test_empty_gzip_response(self):
        """Test decoding empty gzip-compressed response"""
        empty_compressed = gzip.compress(b"")
        
        result = decode_api_response(empty_compressed)
        
        self.assertEqual(result, "")
        self.assertIsInstance(result, str)
    
    def test_json_plain_response(self):
        """Test decoding JSON plain text response"""
        json_string = '{"status": "success", "data": {"campaign_id": 12345}}'
        data_bytes = json_string.encode('utf-8')
        
        result = decode_api_response(data_bytes)
        
        self.assertEqual(result, json_string)
    
    def test_json_gzip_response(self):
        """Test decoding gzip-compressed JSON response"""
        json_string = '{"status": "success", "data": {"campaign_id": 12345}}'
        compressed = gzip.compress(json_string.encode('utf-8'))
        
        result = decode_api_response(compressed)
        
        self.assertEqual(result, json_string)
    
    def test_large_gzip_response(self):
        """Test decoding large gzip-compressed response"""
        # Create a large test string
        large_string = "Lorem ipsum dolor sit amet. " * 1000
        compressed = gzip.compress(large_string.encode('utf-8'))
        
        result = decode_api_response(compressed)
        
        self.assertEqual(result, large_string)
        # Verify compression actually happened
        self.assertLess(len(compressed), len(large_string))
    
    def test_unicode_characters_plain(self):
        """Test decoding plain text with unicode characters"""
        test_string = "Hello 世界 🌍 Ñoño"
        data_bytes = test_string.encode('utf-8')
        
        result = decode_api_response(data_bytes)
        
        self.assertEqual(result, test_string)
    
    def test_unicode_characters_gzip(self):
        """Test decoding gzip-compressed unicode text"""
        test_string = "Hello 世界 🌍 Ñoño"
        compressed = gzip.compress(test_string.encode('utf-8'))
        
        result = decode_api_response(compressed)
        
        self.assertEqual(result, test_string)
    
    def test_single_byte_not_gzip(self):
        """Test that single byte is treated as plain text"""
        data_bytes = b"A"
        
        result = decode_api_response(data_bytes)
        
        self.assertEqual(result, "A")
    
    def test_two_bytes_not_gzip_magic(self):
        """Test that two bytes without gzip magic are treated as plain text"""
        # Use bytes that are NOT 0x1f 0x8b
        data_bytes = b"AB"
        
        result = decode_api_response(data_bytes)
        
        self.assertEqual(result, "AB")
    
    def test_invalid_gzip_raises_error(self):
        """Test that invalid gzip data raises appropriate error"""
        # Create data with gzip magic number but invalid gzip format
        invalid_gzip = b'\x1f\x8b\x00\x00invalid data'
        
        with self.assertRaises(gzip.BadGzipFile):
            decode_api_response(invalid_gzip)
    
    def test_invalid_utf8_plain_raises_error(self):
        """Test that invalid UTF-8 plain text raises UnicodeDecodeError"""
        # Invalid UTF-8 sequence
        invalid_utf8 = b'\xff\xfe\xfd'
        
        with self.assertRaises(UnicodeDecodeError):
            decode_api_response(invalid_utf8)
    
    def test_custom_encoding(self):
        """Test decoding with custom encoding"""
        test_string = "Hello, World!"
        data_bytes = test_string.encode('latin-1')
        
        result = decode_api_response(data_bytes, encoding='latin-1')
        
        self.assertEqual(result, test_string)
    
    def test_real_world_api_response_format(self):
        """Test with realistic API response format"""
        # Simulate a typical Amazon Ads API response
        api_response = """{"campaigns": [
            {"campaignId": 123456, "name": "Test Campaign", "state": "enabled"},
            {"campaignId": 789012, "name": "Another Campaign", "state": "paused"}
        ]}"""
        
        # Test both plain and compressed
        plain_bytes = api_response.encode('utf-8')
        compressed_bytes = gzip.compress(plain_bytes)
        
        result_plain = decode_api_response(plain_bytes)
        result_compressed = decode_api_response(compressed_bytes)
        
        self.assertEqual(result_plain, api_response)
        self.assertEqual(result_compressed, api_response)
        self.assertEqual(result_plain, result_compressed)


class TestGzipDetection(unittest.TestCase):
    """Test cases specifically for gzip magic number detection"""
    
    def test_detects_gzip_magic_number(self):
        """Verify gzip magic number detection works correctly"""
        compressed = gzip.compress(b"test")
        
        # Check magic number is present
        self.assertEqual(compressed[0], 0x1f)
        self.assertEqual(compressed[1], 0x8b)
        
        # Verify our function handles it
        result = decode_api_response(compressed)
        self.assertEqual(result, "test")
    
    def test_does_not_falsely_detect_gzip(self):
        """Ensure we don't falsely detect gzip when it's not there"""
        # Plain text that starts with bytes that look similar but aren't gzip
        # Use valid UTF-8 text instead
        not_gzip = b'some plain text'
        
        result = decode_api_response(not_gzip)
        self.assertEqual(result, not_gzip.decode('utf-8'))


def run_tests():
    """Run all tests and print results"""
    print("=" * 80)
    print("Testing amazon_api_utils.decode_api_response()")
    print("=" * 80)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestDecodeAPIResponse))
    suite.addTests(loader.loadTestsFromTestCase(TestGzipDetection))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1


if __name__ == '__main__':
    exit(run_tests())
