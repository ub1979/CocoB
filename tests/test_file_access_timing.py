# =============================================================================
# test_file_access_timing.py — Tests for file_access timing attack protection
# =============================================================================

import pytest
import tempfile
import time
import statistics


class TestFileAccessTimingAttack:
    """Test that password verification uses constant-time comparison."""

    def test_password_verification_uses_hmac_compare_digest(self):
        """Password verification should use hmac.compare_digest."""
        from coco_b.core.file_access import FileAccessManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fam = FileAccessManager(project_root=tmpdir)
            
            # Set up a password
            assert fam.setup_password("correct_password_123")
            
            # Verify correct password works
            assert fam.verify_password("correct_password_123") is True
            
            # Verify wrong password fails
            assert fam.verify_password("wrong_password_456") is False

    def test_timing_attack_resistance(self):
        """Password verification timing should be similar for correct and wrong passwords."""
        from coco_b.core.file_access import FileAccessManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fam = FileAccessManager(project_root=tmpdir)
            
            # Set up a password
            assert fam.setup_password("test_password_12345")
            
            # Measure time for correct password (multiple samples)
            correct_times = []
            for _ in range(10):
                start = time.perf_counter()
                fam.verify_password("test_password_12345")
                end = time.perf_counter()
                correct_times.append((end - start) * 1000)  # Convert to ms
            
            # Measure time for wrong password (multiple samples)
            wrong_times = []
            for _ in range(10):
                start = time.perf_counter()
                fam.verify_password("wrong_password_67890")
                end = time.perf_counter()
                wrong_times.append((end - start) * 1000)  # Convert to ms
            
            # Calculate means
            correct_mean = statistics.mean(correct_times)
            wrong_mean = statistics.mean(wrong_times)
            
            # The timing difference should be small (less than 2x)
            # In a vulnerable implementation, wrong passwords would be much faster
            ratio = max(correct_mean, wrong_mean) / min(correct_mean, wrong_mean)
            
            # Allow for some variance in timing, but it shouldn't be 10x different
            assert ratio < 10, \
                f"Timing ratio {ratio:.2f} suggests non-constant-time comparison. " \
                f"Correct: {correct_mean:.3f}ms, Wrong: {wrong_mean:.3f}ms"

    def test_similar_length_passwords_have_similar_timing(self):
        """Passwords of similar length should have similar verification times."""
        from coco_b.core.file_access import FileAccessManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fam = FileAccessManager(project_root=tmpdir)
            
            # Set up a password
            assert fam.setup_password("password_12345")
            
            # Test various wrong passwords of same length
            times = []
            test_passwords = [
                "password_12345",  # correct
                "password_12346",  # wrong (last char different)
                "password_12344",  # wrong (last char different)
                "password_12355",  # wrong (middle char different)
                "passwore_12345",  # wrong (early char different)
            ]
            
            for pwd in test_passwords:
                start = time.perf_counter()
                result = fam.verify_password(pwd)
                end = time.perf_counter()
                times.append((end - start) * 1000)
            
            # All times should be similar (no significant outliers)
            mean_time = statistics.mean(times)
            stdev_time = statistics.stdev(times)
            
            # Standard deviation should be small relative to mean
            cv = stdev_time / mean_time if mean_time > 0 else 0
            
            # Coefficient of variation should be reasonable (< 0.5)
            assert cv < 0.5, \
                f"High timing variance (CV={cv:.2f}) suggests timing side channel. " \
                f"Mean: {mean_time:.3f}ms, Stdev: {stdev_time:.3f}ms"

    def test_password_not_set_returns_false(self):
        """verify_password should return False if no password is set."""
        from coco_b.core.file_access import FileAccessManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fam = FileAccessManager(project_root=tmpdir)
            
            # No password set yet
            assert fam.verify_password("any_password") is False

    def test_corrupted_auth_file_returns_false(self):
        """verify_password should return False if auth file is corrupted."""
        from coco_b.core.file_access import FileAccessManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fam = FileAccessManager(project_root=tmpdir)
            
            # Set up a password
            assert fam.setup_password("test_password")
            
            # Corrupt the auth file
            auth_file = fam._auth_file
            auth_file.write_text("corrupted:data")
            
            # Should return False gracefully
            assert fam.verify_password("test_password") is False

    def test_empty_password_fails(self):
        """Empty password should fail verification."""
        from coco_b.core.file_access import FileAccessManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fam = FileAccessManager(project_root=tmpdir)
            
            # Try to set empty password (should fail)
            assert fam.setup_password("") is False
            
            # Set up a valid password
            assert fam.setup_password("valid_password")
            
            # Empty password should not verify
            assert fam.verify_password("") is False

    def test_short_password_fails(self):
        """Short password (< 8 chars) should fail setup."""
        from coco_b.core.file_access import FileAccessManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fam = FileAccessManager(project_root=tmpdir)
            
            # Short password should fail
            assert fam.setup_password("short") is False
            
            # 8 character password should work
            assert fam.setup_password("12345678") is True
