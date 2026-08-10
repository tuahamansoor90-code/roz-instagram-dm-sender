import sys
import hmac
import hashlib
import base64
from datetime import datetime, date

# Must match the SECRET_KEY in license_verifier.py exactly
SECRET_KEY = b"roz_instagram_dm_sender_secure_secret_key_2026"

def generate_key_from_data(start_date_obj, end_date_obj, target_hwid):
    """
    Packs dates and HWID, signs with HMAC-SHA256, and generates a formatted Base32 key.
    """
    start_yr = start_date_obj.year - 2000
    start_mo = start_date_obj.month
    start_dy = start_date_obj.day
    
    end_yr = end_date_obj.year - 2000
    end_mo = end_date_obj.month
    end_dy = end_date_obj.day
    
    # Check bounds
    if not (0 <= start_yr <= 255) or not (0 <= end_yr <= 255):
        raise ValueError("Years must be between 2000 and 2255.")
        
    if target_hwid.upper() == "ANY":
        hwid_bytes = b'\xff' * 8
    else:
        # Standardize HWID format
        clean_hwid = target_hwid.upper().strip()
        if len(clean_hwid) != 16:
            raise ValueError("Hardware ID must be exactly 16 hex characters.")
        hwid_bytes = bytes.fromhex(clean_hwid)
        
    # Pack parameters (14 bytes total)
    payload = bytes([start_yr, start_mo, start_dy, end_yr, end_mo, end_dy]) + hwid_bytes
    
    # Sign payload (8 bytes signature)
    sig = hmac.new(SECRET_KEY, payload, hashlib.sha256).digest()[:8]
    
    # Combine (22 bytes total)
    key_bytes = payload + sig
    
    # Base32 Encode (36 chars without padding)
    b32_str = base64.b32encode(key_bytes).decode().rstrip("=")
    
    # Format key into groups of 6 characters: XXXXXX-XXXXXX-XXXXXX-XXXXXX-XXXXXX-XXXXXX
    key_formatted = "-".join(b32_str[i:i+6] for i in range(0, len(b32_str), 6))
    return key_formatted

def main():
    print("=" * 60)
    print("           INSTAGRAM DM SENDER KEY GENERATOR           ")
    print("=" * 60)
    
    # Get Start Date
    start_date_str = input("Enter License Start Date (YYYY-MM-DD) [Default: Today]: ").strip()
    if not start_date_str:
        start_date_obj = date.today()
    else:
        try:
            start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            print("[ERROR] Invalid date format! Please use YYYY-MM-DD.")
            sys.exit(1)
            
    # Get End Date
    end_date_str = input("Enter License Expiry Date (YYYY-MM-DD): ").strip()
    if not end_date_str:
        print("[ERROR] Expiry date is required.")
        sys.exit(1)
    try:
        end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError:
        print("[ERROR] Invalid date format! Please use YYYY-MM-DD.")
        sys.exit(1)
        
    if end_date_obj < start_date_obj:
        print("[ERROR] Expiry date cannot be earlier than start date.")
        sys.exit(1)
        
    # Get HWID
    hwid = input("Enter Customer HWID (or type 'ANY' for unrestricted): ").strip()
    if not hwid:
        print("[ERROR] HWID or 'ANY' is required.")
        sys.exit(1)
        
    try:
        key = generate_key_from_data(start_date_obj, end_date_obj, hwid)
        print("\n" + "-" * 60)
        print("LICENSE DETAILS:")
        print(f"  Start Date: {start_date_obj}")
        print(f"  Expiry Date: {end_date_obj}")
        print(f"  Hardware ID: {hwid.upper()}")
        print("-" * 60)
        print(f"Generated Key:\n\n  \033[92m{key}\033[0m\n")
        print("-" * 60)
        print("Share the Generated Key with your customer.")
    except Exception as e:
        print(f"[ERROR] Failed to generate key: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    finally:
        input("\nPress Enter to exit...")
