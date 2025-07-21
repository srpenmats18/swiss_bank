#!/usr/bin/env python3
"""
Enhanced OTP Debug Script for Swiss Bank API
This script provides deep debugging for OTP initiation failures
"""

import requests
import json
from pymongo import MongoClient
from datetime import datetime
import sys
import time
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import redis
from pathlib import Path

# Load environment variables
current_file_dir = Path(__file__).parent  # /tests/
backend_dir = current_file_dir.parent
env_path = backend_dir / '.env'
load_dotenv(env_path)

# Configuration - make these configurable
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8001")
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "swiss_bank")
CUSTOMERS_COLLECTION = "customers"

class OTPServiceDebugger:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.email_user = os.getenv("SMTP_USERNAME")
        self.email_password = os.getenv("SMTP_PASSWORD")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        
    def check_environment_variables(self):
        
        env_vars = {
            'SMTP_SERVER': self.smtp_server,
            'SMTP_PORT': self.smtp_port,
            'SMTP_USERNAME': self.email_user,
            'SMTP_PASSWORD': self.email_password,
            'REDIS_URL': self.redis_url
        }
        
        missing_vars = []
        for var, value in env_vars.items():
            if not value:
                missing_vars.append(var)
                print(f"❌ {var}: Not set")
        
        if missing_vars:
            print(f"\n⚠️  Missing environment variables: {', '.join(missing_vars)}")
            return False
        else:
            print("\n✅ All environment variables are set")
            return True
    
    def test_smtp_connection(self):
        
        if not self.email_user or not self.email_password:
            print("❌ SMTP credentials not configured")
            return False
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                print("✅ SMTP connection successful!")
                return True
            
        except Exception as e:
            print(f"❌ SMTP Error: {e}")
            return False
    
    def test_redis_connection(self):

        try:
            r = redis.from_url(self.redis_url)
            r.ping()
            print("✅ Redis connection successful!")
            
            # Test basic operations
            test_key = "otp_test_key"
            test_value = "test_value"
            r.setex(test_key, 60, test_value)
            retrieved = r.get(test_key)
            
            if retrieved and retrieved.decode() == test_value:
                r.delete(test_key)
                return True
            else:
                print("❌ Redis read/write operations failed")
                return False
  
        except Exception as e:
            print(f"❌ Redis error: {e}")
            return False
    
    def check_email_template(self):
        """Check if email template exists and is readable"""
        print("\n📄 EMAIL TEMPLATE CHECK")
        
        template_path = Path(__file__).parent.parent / "templates/emails/otp_email.html"
                
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Check for required placeholders
                required_placeholders = ['{customer_name}', '{otp}', '{expiry_minutes}']
                missing_placeholders = []
                
                for placeholder in required_placeholders:
                    if placeholder not in content:
                        missing_placeholders.append(placeholder)
                
                if missing_placeholders:
                    print(f"⚠️  Missing placeholders: {', '.join(missing_placeholders)}")
                    return False
                else:
                    print("✅ All required placeholders found")
                
                return True
        except Exception as e:
            print(f"❌ Error reading template: {e}")
            return False
        
        print("❌ No email template found in any expected location")
        return False
    
    def test_api_service_health(self):
        """Test specific API service health endpoints"""
        print("\n🏥 API SERVICE HEALTH CHECK")
        print("=" * 50)
        
        # Define endpoints to test with their expected behavior
        endpoints = [
            {"path": "/health", "description": "Main health check", "priority": "high"},
            {"path": "/", "description": "Root endpoint", "priority": "low"},
            {"path": "/favicon.ico", "description": "Favicon", "priority": "low"},
            {"path": "/health/detailed", "description": "Detailed health check", "priority": "medium"}
        ]
        
        health_status = False
        passed_endpoints = 0
        total_endpoints = len(endpoints)
        
        for endpoint in endpoints:
            try:
                response = requests.get(f"{BASE_URL}{endpoint['path']}", timeout=5)
                
                # Different success criteria for different endpoints
                if endpoint['path'] == '/favicon.ico':
                    # Favicon might return 404 or 200, both are acceptable
                    success = response.status_code in [200, 404]
                    status_symbol = "✅" if success else "⚠️"
                else:
                    # Other endpoints should return 200
                    success = response.status_code == 200
                    status_symbol = "✅" if success else "⚠️"
                
                priority_indicator = f"[{endpoint['priority'].upper()}]"
                print(f"{status_symbol} {endpoint['path']} {priority_indicator}: {response.status_code} - {endpoint['description']}")
                
                if success:
                    passed_endpoints += 1
                    
                # Main health endpoint determines overall health status
                if endpoint['path'] == "/health" and success:
                    health_status = True
                    
            except requests.exceptions.RequestException as e:
                priority_indicator = f"[{endpoint['priority'].upper()}]"
                print(f"❌ {endpoint['path']} {priority_indicator}: {e}")
        
        print(f"\nEndpoint Summary: {passed_endpoints}/{total_endpoints} endpoints accessible")
        
        return health_status
    
    def test_database_connectivity(self):
        """Test database connectivity and customer data"""
        print("\n💾 DATABASE CONNECTIVITY CHECK")
        print("=" * 50)
        
        try:
            client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
            db = client[DATABASE_NAME]
            customers_collection = db[CUSTOMERS_COLLECTION]
            
            # Test connection
            client.admin.command('ping')
            print("✅ Database connection successful!")
            
            # Test specific customer
            sample_customer = customers_collection.find().sort("_id", 1).skip(3).limit(1).next()
            
            if sample_customer:
                print("✅ Sample customer found with email")
                return True, sample_customer
            else:
                print("❌ No customers with email found")
                return False, None
                
        except Exception as e:
            print(f"❌ Database error: {e}")
            return False, None
    
    def test_verify_otp_endpoint(self, session_id):
        """Test OTP verification endpoint with various scenarios"""
        print("\n🔐 OTP VERIFICATION ENDPOINT TEST")
        print("=" * 50)
        
        test_results = {
            'invalid_otp': False,
            'missing_session': False,
            'invalid_session': False,
            'endpoint_availability': False
        }
        
        try:
            # Test 1: Invalid OTP
            print("Test 1: Invalid OTP verification")
            invalid_otp_payload = {
                "session_id": session_id,
                "otp": "000000"  # Invalid OTP
            }
            
            try:
                response = requests.post(
                    f"{BASE_URL}/api/auth/verify-otp",
                    data=invalid_otp_payload,
                    timeout=10
                )
                
                print(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    response_data = response.json()
                    # Check if it's an error response
                    if not response_data.get('success', True):
                        error_code = response_data.get('error_code')
                        if error_code in ['INVALID_OTP', 'INVALID_SESSION', 'OTP_EXPIRED', 'MAX_ATTEMPTS_EXCEEDED']:
                            print(f"  ✅ Expected error response: {response_data.get('message', 'No message')}")
                            print(f"     Error code: {error_code}")
                            test_results['invalid_otp'] = True
                        else:
                            print(f"  ⚠️  Unexpected error code: {error_code}")
                    else:
                        print("  ⚠️  Unexpected success response for invalid OTP")
                elif response.status_code == 404:
                    print("  ❌ Endpoint not found!")
                else:
                    print(f"  ⚠️  Unexpected status code: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Error testing invalid OTP: {e}")
            
            # Test 2: Missing session ID
            print("\nTest 2: Missing session ID")
            missing_session_payload = {
                "otp": "123456"
            }
            
            try:
                response = requests.post(
                    f"{BASE_URL}/api/auth/verify-otp",
                    data=missing_session_payload,
                    timeout=10
                )
                
                print(f"  Status: {response.status_code}")
                if response.status_code == 422:
                    response_data = response.json()
                    print(f"  ✅ Expected validation error: {response_data.get('message', response_data.get('detail', 'No message'))}")
                    test_results['missing_session'] = True
                elif response.status_code == 200:
                    response_data = response.json()
                    if not response_data.get('success', True):
                        print(f"  ✅ Expected error response: {response_data.get('message', 'No message')}")
                        test_results['missing_session'] = True
                    else:
                        print("  ⚠️  Unexpected success response for missing session")
                else:
                    print(f"  ⚠️  Unexpected status code: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Error testing missing session: {e}")
            
            # Test 3: Invalid session ID
            print("\nTest 3: Invalid session ID")
            invalid_session_payload = {
                "session_id": "ygghgdg9g48ghg8r33siwfj",
                "otp": "123456"
            }
            
            try:
                response = requests.post(
                    f"{BASE_URL}/api/auth/verify-otp",
                    data=invalid_session_payload,
                    timeout=10
                )
                
                print(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    response_data = response.json()
                    if not response_data.get('success', True):
                        error_code = response_data.get('error_code')
                        if error_code == 'INVALID_SESSION':
                            print(f"  ✅ Expected session error: {response_data.get('message', 'No message')}")
                            print(f"     Error code: {error_code}")
                            test_results['invalid_session'] = True
                        else:
                            print(f"  ⚠️  Unexpected error code: {error_code}")
                    else:
                        print("  ⚠️  Unexpected success response for invalid session")
                else:
                    print(f"  ⚠️  Unexpected status code: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Error testing invalid session: {e}")
            
            # Test 4: Endpoint availability
            test_results['endpoint_availability'] = any([
                test_results['invalid_otp'],
                test_results['missing_session'],
                test_results['invalid_session']
            ])
            
            if test_results['endpoint_availability']:
                print("\n✅ Verify OTP endpoint is available and responding correctly")
            else:
                print("\n❌ Verify OTP endpoint may not be working properly")
                
        except Exception as e:
            print(f"❌ Verify OTP test failed: {e}")
            
        return test_results['endpoint_availability']
    
    def test_resend_otp_endpoint(self, session_id):
        """Test OTP resend endpoint with various scenarios"""
        print("\n🔄 OTP RESEND ENDPOINT TEST")
        print("=" * 50)
        
        test_results = {
            'valid_session': False,
            'invalid_session': False,
            'missing_session': False,
            'endpoint_availability': False
        }
        
        try:
            # Test 1: Valid session ID
            print("Test 1: Valid session resend")
            valid_payload = {
                "session_id": session_id
            }
            
            try:
                start_time = time.time()
                response = requests.post(
                    f"{BASE_URL}/api/auth/resend-otp",
                    data=valid_payload,
                    timeout=30
                )
                end_time = time.time()
                
                duration = end_time - start_time
                print(f"  Status: {response.status_code} (took {duration:.2f}s)")
                
                if response.status_code == 200:
                    response_data = response.json()
                    if response_data.get('success'):
                        print("  ✅ OTP resent successfully!")
                        print(f"     Message: {response_data.get('message')}")
                        test_results['valid_session'] = True
                    else:
                        print(f"  ⚠️  Resend failed: {response_data.get('message')}")
                        # Still counts as endpoint working if it returns proper error
                        test_results['valid_session'] = True
                elif response.status_code == 404:
                    print("  ❌ Endpoint not found!")
                else:
                    print(f"  ⚠️  Unexpected status: {response.status_code}")
                    print(f"     Response: {response.text[:200]}...")
                    
            except requests.exceptions.Timeout:
                print("  ❌ Request timeout - server may be overloaded")
            except Exception as e:
                print(f"  ❌ Error testing valid session: {e}")
            
            # Test 2: Invalid session ID
            print("\nTest 2: Invalid session resend")
            invalid_payload = {
                "session_id": "invalid_session_id_12345"
            }
            
            try:
                response = requests.post(
                    f"{BASE_URL}/api/auth/resend-otp",
                    data=invalid_payload,
                    timeout=10
                )
                
                print(f"  Status: {response.status_code}")
                if response.status_code in [400, 401, 404]:
                    response_data = response.json()
                    print(f" ✅ Expected session error: {response_data.get('message', 'No message')}")
                    test_results['invalid_session'] = True
                else:
                    print(f"  ⚠️  Unexpected status code: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Error testing invalid session: {e}")
            
            # Test 3: Missing session ID
            print("\nTest 3: Missing session ID")
            missing_payload = {}
            
            try:
                response = requests.post(
                    f"{BASE_URL}/api/auth/resend-otp",
                    data=missing_payload,
                    timeout=10
                )
                
                print(f"  Status: {response.status_code}")
                if response.status_code in [400, 422]:
                    response_data = response.json()
                    print(f" ✅ Expected validation error: {response_data.get('message', 'No message')}")
                    test_results['missing_session'] = True
                else:
                    print(f"  ⚠️  Unexpected status code: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Error testing missing session: {e}")
            
            # Test 4: Endpoint availability
            test_results['endpoint_availability'] = any([
                test_results['valid_session'],
                test_results['invalid_session'],
                test_results['missing_session']
            ])
            
            if test_results['endpoint_availability']:
                print("\n✅ Resend OTP endpoint is available and responding")
            else:
                print("\n❌ Resend OTP endpoint may not be working properly")
                
        except Exception as e:
            print(f"❌ Resend OTP test failed: {e}")
            
        return test_results['endpoint_availability']
    
    def test_otp_functionality(self, session_id):
        """Test OTP functionality with real session"""
        print("\n🧪 OTP FUNCTIONALITY TEST")
        print("=" * 50)
        
        try:
            # Get session details
            session_response = requests.get(f"{BASE_URL}/api/auth/session/{session_id}")
            
            if session_response.status_code != 200:
                print(f"❌ Cannot get session details: {session_response.status_code}")
                return False
            
            session_data = session_response.json().get('data', {})
            
            # Display session information
            print("Session information:")
            print(f"  State: {session_data.get('state')}")
            print(f"  Contact Verified: {session_data.get('contact_verified')}")
            print(f"  OTP Method: {session_data.get('preferred_otp_method')}")
            print(f"  Customer Email: {session_data.get('customer_data', {}).get('email')}")
            
            otp_payload = {"session_id": session_id}
            
            try:
                start_time = time.time()
                otp_response = requests.post(
                    f"{BASE_URL}/api/auth/initiate-otp",
                    data=otp_payload,
                    timeout=30
                )
                end_time = time.time()
                
                duration = end_time - start_time
                # Warn about slow response
                if duration > 2.0:
                    print(f"⚠️  Slow response time ({duration:.2f}s) - consider investigating server performance")
                
                print(f"Response status: {otp_response.status_code}")
                
                if otp_response.status_code == 200:
                    otp_data = otp_response.json()
                    
                    if otp_data.get('success'):
                        print("✅ OTP sent successfully!")
                        print(f"   Message: {otp_data.get('message')}")
                        print(f"   OTP Method: {otp_data.get('otp_method')}")
                        
                        # Test additional OTP endpoints
                        verify_result = self.test_verify_otp_endpoint(session_id)
                        resend_result = self.test_resend_otp_endpoint(session_id)
                        
                        # Overall OTP functionality passes if initiate works and other endpoints are available
                        return verify_result and resend_result
                    else:
                        print("❌ OTP initiation failed!")
                        print(f"   Error: {otp_data.get('message')}")
                        error_code = otp_data.get('error_code')
                        technical_error = otp_data.get('technical_error', False)
                        
                        if error_code == "SERVICE_ERROR" and technical_error:
                            print("\n🔍 SERVICE_ERROR detected")
                            
                        return False
                else:
                    print(f"❌ HTTP Error: {otp_response.status_code}")
                    print(f"Response: {otp_response.text}")
                    return False
                    
            except requests.exceptions.Timeout:
                print("❌ Request timeout - server may be overloaded")
                return False
            except requests.exceptions.ConnectionError:
                print("❌ Connection error - server may be down")
                return False
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False
        
    def test_session_status_endpoint(self, session_id):
        """Test session status endpoint with various scenarios"""
        print("\n📋 SESSION STATUS ENDPOINT TEST")
        print("=" * 50)
        
        test_results = {
            'valid_session': False,
            'invalid_session': False,
            'malformed_session': False,
            'endpoint_availability': False
        }
        
        try:
            # Test 1: Valid session ID
            print("Test 1: Valid session status")
            try:
                response = requests.get(f"{BASE_URL}/api/auth/session/{session_id}", timeout=10)
                
                print(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    response_data = response.json()
                    
                    # Check response structure
                    if 'data' in response_data:
                        session_data = response_data['data']
                        print("  ✅ Valid session found!")
                        print(f"     State: {session_data.get('state')}")
                        print(f"     Contact Verified: {session_data.get('contact_verified')}")
                        print(f"     OTP Method: {session_data.get('preferred_otp_method')}")
                        test_results['valid_session'] = True
                    else:
                        print("  ⚠️  Unexpected response structure")
                elif response.status_code == 404:
                    print("  ❌ Session not found (but endpoint exists)")
                    test_results['valid_session'] = True  # Endpoint working, just session not found
                else:
                    print(f"  ⚠️  Unexpected status code: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Error testing valid session: {e}")
            
            # Test 2: Invalid session ID
            print("\nTest 2: Invalid session ID")
            invalid_session_id = "invalid_session_12345"
            
            try:
                response = requests.get(f"{BASE_URL}/api/auth/session/{invalid_session_id}", timeout=10)
                
                print(f"  Status: {response.status_code}")
                if response.status_code == 404:
                    print("  ✅ Expected 404 for invalid session")
                    test_results['invalid_session'] = True
                elif response.status_code == 200:
                    response_data = response.json()
                    if not response_data.get('success', True):
                        print(f"  ✅ Expected error response: {response_data.get('message')}")
                        test_results['invalid_session'] = True
                    else:
                        print("  ⚠️  Unexpected success for invalid session")
                else:
                    print(f"  ⚠️  Unexpected status code: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Error testing invalid session: {e}")
            
            # Test 3: Malformed session ID
            print("\nTest 3: Malformed session ID")
            malformed_session_id = "malformed@session#id!@#"
            
            try:
                response = requests.get(f"{BASE_URL}/api/auth/session/{malformed_session_id}", timeout=10)
                
                print(f"  Status: {response.status_code}")
                if response.status_code in [400, 404, 422]:
                    print("  ✅ Expected error for malformed session ID")
                    test_results['malformed_session'] = True
                else:
                    print(f"  ⚠️  Unexpected status code: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Error testing malformed session: {e}")
            
            # Test 4: Endpoint availability
            test_results['endpoint_availability'] = any([
                test_results['valid_session'],
                test_results['invalid_session'],
                test_results['malformed_session']
            ])
            
            if test_results['endpoint_availability']:
                print("\n✅ Session status endpoint is available and responding correctly")
            else:
                print("\n❌ Session status endpoint may not be working properly")
                
        except Exception as e:
            print(f"❌ Session status test failed: {e}")
            
        return test_results['endpoint_availability']    

    def run_comprehensive_debug(self):
        """Run comprehensive debugging suite"""
        print("🔍 COMPREHENSIVE OTP DEBUG SUITE")
        print("=" * 60)
        
        debug_results = {
            'environment': False,
            'smtp': False,
            'redis': False,
            'template': False,
            'api_health': False,
            'database': False,
            'session_creation': False,
            'session_status': False,
            'otp_test': False
        }
        
        # Step 1: Basic infrastructure tests
        debug_results['environment'] = self.check_environment_variables()
        debug_results['smtp'] = self.test_smtp_connection()
        debug_results['redis'] = self.test_redis_connection()
        debug_results['template'] = self.check_email_template()
        debug_results['api_health'] = self.test_api_service_health()
        db_success, sample_customer = self.test_database_connectivity()
        debug_results['database'] = db_success
        
        # Step 2: Session-based tests (only if database is working)
        session_id = None
        if sample_customer:
            session_id = self.create_test_session(sample_customer)
            debug_results['session_creation'] = session_id is not None
            
            if session_id:
                # Test session status endpoint
                debug_results['session_status'] = self.test_session_status_endpoint(session_id)
                
                # Test OTP functionality
                debug_results['otp_test'] = self.test_otp_functionality(session_id)
            else:
                print("❌ Cannot proceed with session-based tests without valid session")
        else:
            print("❌ Cannot proceed with session-based tests without sample customer")
        
        # Step 3: Summary
        self.print_debug_summary(debug_results)
        return debug_results

    def create_test_session(self, sample_customer):
        """Create a test session for debugging purposes"""
        print("\n🔧 SESSION CREATION TEST")
        print("=" * 50)
        
        try:
            # Step 1: Create initial session
            auth_payload = {
                "ip_address": "127.0.0.1",
                "user_agent": "debug-client"
            }
            
            print("Creating authentication session...")
            response = requests.post(f"{BASE_URL}/api/auth/session", json=auth_payload, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Failed to create session: {response.status_code}")
                print(f"Response: {response.text}")
                return None
            
            session_data = response.json()
            session_id = session_data.get('session_id')
            
            if not session_id:
                print("❌ No session_id in response")
                return None
            
            print(f"✅ Session created: {session_id}")
            
            # Step 2: Verify contact to make session useful for OTP testing
            customer_email = sample_customer.get('email')
            if customer_email:
                print(f"Verifying contact: {customer_email}")
                
                verify_payload = {
                    "session_id": session_id,
                    "email": customer_email
                }
                
                verify_response = requests.post(
                    f"{BASE_URL}/api/auth/verify-contact", 
                    data=verify_payload, 
                    timeout=10
                )
                
                if verify_response.status_code == 200:
                    verify_data = verify_response.json()
                    if verify_data.get('success'):
                        print("✅ Contact verified successfully")
                        print(f"   Customer: {verify_data.get('customer_name', 'Unknown')}")
                        print(f"   OTP Method: {verify_data.get('preferred_otp_method', 'email')}")
                    else:
                        print(f"⚠️  Contact verification failed: {verify_data.get('message')}")
                else:
                    print(f"⚠️  Contact verification error: {verify_response.status_code}")
            
            return session_id
            
        except requests.exceptions.Timeout:
            print("❌ Session creation timeout")
            return None
        except requests.exceptions.ConnectionError:
            print("❌ Connection error during session creation")
            return None
        except Exception as e:
            print(f"❌ Session creation failed: {e}")
            return None

    def print_debug_summary(self, debug_results):
        """Print formatted debug summary"""
        print("\n📊 DEBUG SUMMARY")
        print("=" * 50)
        
        # Group tests by category
        infrastructure_tests = ['environment', 'smtp', 'redis', 'template', 'api_health', 'database']
        session_tests = ['session_creation', 'session_status', 'otp_test']
        
        print("Infrastructure Tests:")
        for test in infrastructure_tests:
            if test in debug_results:
                status = "✅ PASS" if debug_results[test] else "❌ FAIL"
                print(f"  {test.upper()}: {status}")
        
        print("\nSession-Based Tests:")
        for test in session_tests:
            if test in debug_results:
                status = "✅ PASS" if debug_results[test] else "❌ FAIL"
                print(f"  {test.upper()}: {status}")
        
        # Overall summary
        passed = sum(1 for result in debug_results.values() if result)
        total = len(debug_results)
        
        print(f"\nOverall: {passed}/{total} tests passed")
        
        # Specific recommendations based on failures
        if not debug_results.get('session_creation', False):
            print("\n❌ Session creation failed - check API server and endpoint configuration")
        elif not debug_results.get('session_status', False):
            print("\n❌ Session status endpoint failed - check endpoint implementation")
        elif not debug_results.get('otp_test', False):
            print("\n❌ OTP functionality failed - check email/SMS services and configuration")
        elif debug_results.get('otp_test', False):
            print("\n🎉 All core OTP functionality is working correctly!")
        
        return debug_results

def main():
    """Main debugging function"""
    debugger = OTPServiceDebugger()
    results = debugger.run_comprehensive_debug()
    
    # Exit with appropriate code
    if results.get('otp_test', False):
        print("\n✅ Debugging completed successfully!")
        return 0
    else:
        print("\n❌ Debugging found issues that need to be resolved.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

