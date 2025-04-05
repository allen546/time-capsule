"""
SSL Configuration for Time Capsule Application

This module provides SSL context creation for secure connections.
"""

import ssl
import os
from typing import Dict, Optional, Tuple, Any

def create_ssl_context(cert_path: str, key_path: str, 
                      password: Optional[str] = None) -> ssl.SSLContext:
    """
    Create an SSL context for the Sanic application.
    
    Args:
        cert_path: Path to the SSL certificate file
        key_path: Path to the SSL private key file
        password: Optional password for the private key
    
    Returns:
        An SSL context object
    """
    # Create SSL context with strong security settings
    context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    
    # Set protocols to TLS 1.2 and TLS 1.3 only
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    
    # Set strong cipher suite
    context.set_ciphers('ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384')
    
    # Disable compression to prevent CRIME attacks
    context.options |= ssl.OP_NO_COMPRESSION
    
    # Load certificate and private key
    context.load_cert_chain(
        certfile=cert_path,
        keyfile=key_path,
        password=password
    )
    
    return context

def get_ssl_dict(cert_dir: str, 
                cert_name: str = "fullchain.pem", 
                key_name: str = "privkey.pem",
                password: Optional[str] = None) -> Dict[str, Any]:
    """
    Get SSL configuration as a dictionary for Sanic.
    
    Args:
        cert_dir: Directory containing certificates
        cert_name: Certificate filename
        key_name: Private key filename
        password: Optional password for the private key
    
    Returns:
        Dictionary with SSL configuration
    """
    cert_path = os.path.join(cert_dir, cert_name)
    key_path = os.path.join(cert_dir, key_name)
    
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        raise FileNotFoundError(f"Certificate files not found in {cert_dir}")
    
    return {
        "cert": cert_path,
        "key": key_path,
        "password": password
    } 