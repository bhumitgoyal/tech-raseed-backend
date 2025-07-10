#!/usr/bin/env python3
"""
Bill Splitter with UPI Payment Links
Splits bills from processed receipts among selected contacts and generates UPI payment requests
"""

import json
import os
import webbrowser
import urllib.parse
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import argparse

class BillSplitter:
    """Bill splitting service that works with processed receipt data and generates UPI payment links"""
    
    def __init__(self, receipt_file="pipeline_receipt.json"):
        self.receipt_file = receipt_file
        self.receipts = self._load_receipts()
        
        # Hardcoded contacts (simulate getting from "your contacts")
        self.contacts = {
            "1": {"name": "bhumit", "phone": "+919818646823", "email": "alex.j@email.com"},
            "2": {"name": "Sarah Chen", "phone": "+919205704825", "email": "sarah.chen@email.com"},
            "3": {"name": "Mike Rodriguez", "phone": "+919876543212", "email": "mike.r@email.com"},
            "4": {"name": "Emma Wilson", "phone": "+919876543213", "email": "emma.w@email.com"},
            "5": {"name": "David Kim", "phone": "+919876543214", "email": "david.kim@email.com"},
            "6": {"name": "You", "phone": "+919205704825", "email": "you@email.com"}  # User
        }
        
        # UPI details for payment collection
        self.upi_details = {
            "payee_vpa": "9205704825@ptsbi",  # Your UPI ID
            "payee_name": "Maisha",  # Your name for UPI
        }
    
    def _load_receipts(self) -> List[Dict[str, Any]]:
        """Load receipts from the pipeline JSON file"""
        if not Path(self.receipt_file).exists():
            print(f"❌ No receipts found at {self.receipt_file}")
            print("💡 Process some receipts first using: ./process_receipt.sh <image>")
            return []
        
        try:
            with open(self.receipt_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                return data
            else:
                return [data]  # Convert single receipt to list
                
        except Exception as e:
            print(f"❌ Error loading receipts: {e}")
            return []
    
    def show_recent_receipts(self, limit=10):
        """Display recent receipts for selection"""
        if not self.receipts:
            return []
        
        print("\n📋 RECENT RECEIPTS")
        print("=" * 50)
        
        # Sort by processed_at timestamp (most recent first)
        sorted_receipts = sorted(
            self.receipts, 
            key=lambda x: x.get('processed_at', ''), 
            reverse=True
        )[:limit]
        
        for i, receipt in enumerate(sorted_receipts, 1):
            store = receipt.get('store_name', 'Unknown Store')
            category = receipt.get('receipt_category', 'Unknown')
            total = receipt.get('total_amount', '0')
            currency = receipt.get('currency', '')
            date = receipt.get('date', 'Unknown Date')
            
            print(f"{i:2d}. 🏪 {store}")
            print(f"     📂 {category} | 💰 {currency}{total} | 📅 {date}")
        
        print("=" * 50)
        return sorted_receipts
    
    def show_contacts(self):
        """Display available contacts for selection"""
        print("\n👥 YOUR CONTACTS")
        print("=" * 40)
        
        for contact_id, contact in self.contacts.items():
            icon = "👤" if contact['name'] != "You" else "🫵"
            print(f"{contact_id}. {icon} {contact['name']}")
            print(f"   📱 {contact['phone']}")
            print(f"   📧 {contact['email']}")
            print()
    
    def select_receipt(self) -> Optional[Dict[str, Any]]:
        """Allow user to select a receipt to split"""
        recent_receipts = self.show_recent_receipts()
        
        if not recent_receipts:
            return None
        
        while True:
            try:
                choice = input(f"\n🎯 Select receipt to split (1-{len(recent_receipts)}): ").strip()
                if not choice:
                    return None
                
                index = int(choice) - 1
                if 0 <= index < len(recent_receipts):
                    return recent_receipts[index]
                else:
                    print(f"❌ Please enter a number between 1 and {len(recent_receipts)}")
            except ValueError:
                print("❌ Please enter a valid number")
    
    def select_contacts(self) -> List[Dict[str, Any]]:
        """Allow user to select contacts to split with"""
        self.show_contacts()
        
        print("💡 Enter contact numbers separated by commas (e.g., 1,3,6)")
        print("💡 Press Enter without selection to cancel")
        
        while True:
            try:
                choice = input("\n👥 Select contacts to split with: ").strip()
                if not choice:
                    return []
                
                # Parse contact IDs
                contact_ids = [id.strip() for id in choice.split(',')]
                selected_contacts = []
                
                for contact_id in contact_ids:
                    if contact_id in self.contacts:
                        selected_contacts.append(self.contacts[contact_id])
                    else:
                        print(f"❌ Invalid contact ID: {contact_id}")
                        continue
                
                if selected_contacts:
                    return selected_contacts
                else:
                    print("❌ No valid contacts selected")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def calculate_split(self, receipt: Dict[str, Any], contacts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Calculate bill split among selected contacts"""
        total_amount = float(receipt.get('total_amount', 0))
        currency = receipt.get('currency', '')
        num_people = len(contacts)
        
        if total_amount <= 0 or num_people <= 0:
            return None
        
        # Calculate split amounts
        amount_per_person = total_amount / num_people
        
        # Handle rounding (last person pays the difference)
        rounded_amounts = [round(amount_per_person, 2)] * (num_people - 1)
        last_amount = round(total_amount - sum(rounded_amounts), 2)
        rounded_amounts.append(last_amount)
        
        # Create split summary
        split_data = {
            "receipt_info": {
                "store_name": receipt.get('store_name', 'Unknown Store'),
                "date": receipt.get('date', 'Unknown Date'),
                "total_amount": total_amount,
                "currency": currency,
                "category": receipt.get('receipt_category', 'Unknown')
            },
            "split_details": {
                "total_people": num_people,
                "amount_per_person": amount_per_person,
                "splits": []
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Assign amounts to contacts
        for i, contact in enumerate(contacts):
            split_data["split_details"]["splits"].append({
                "name": contact["name"],
                "phone": contact["phone"],
                "email": contact["email"],
                "amount": rounded_amounts[i],
                "currency": currency
            })
        
        return split_data
    
    def display_split_summary(self, split_data: Optional[Dict[str, Any]]):
        """Display the bill split summary"""
        if not split_data:
            print("❌ Unable to calculate split")
            return
        
        receipt = split_data["receipt_info"]
        splits = split_data["split_details"]["splits"]
        
        print("\n" + "=" * 60)
        print("💸 BILL SPLIT SUMMARY")
        print("=" * 60)
        
        # Receipt info
        print(f"🏪 Store: {receipt['store_name']}")
        print(f"📅 Date: {receipt['date']}")
        print(f"📂 Category: {receipt['category']}")
        print(f"💰 Total: {receipt['currency']}{receipt['total_amount']}")
        print(f"👥 Split among: {split_data['split_details']['total_people']} people")
        
        print(f"\n💵 AMOUNT PER PERSON: {receipt['currency']}{split_data['split_details']['amount_per_person']:.2f}")
        
        print(f"\n👥 INDIVIDUAL AMOUNTS:")
        print("-" * 40)
        
        for split in splits:
            icon = "🫵" if split['name'] == "You" else "👤"
            print(f"{icon} {split['name']:<20} {receipt['currency']}{split['amount']:.2f}")
            print(f"   📱 {split['phone']}")
            print(f"   📧 {split['email']}")
            print()
        
        # Verification
        total_split = sum(split['amount'] for split in splits)
        print(f"✅ Verification: {receipt['currency']}{total_split:.2f} = {receipt['currency']}{receipt['total_amount']}")
        print("=" * 60)
    
    def save_split_record(self, split_data: Optional[Dict[str, Any]], filename="bill_splits.json"):
        """Save the split record for future reference"""
        if not split_data:
            print("❌ No split data to save")
            return
            
        try:
            # Load existing splits
            splits_history = []
            if Path(filename).exists():
                with open(filename, 'r', encoding='utf-8') as f:
                    splits_history = json.load(f)
            
            # Add new split
            splits_history.append(split_data)
            
            # Save updated history
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(splits_history, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Split record saved to {filename}")
            
        except Exception as e:
            print(f"❌ Error saving split record: {e}")
    
    def generate_share_message(self, split_data: Optional[Dict[str, Any]]) -> str:
        """Generate a shareable message for the bill split"""
        if not split_data:
            return ""
        
        receipt = split_data["receipt_info"]
        splits = split_data["split_details"]["splits"]
        
        message = f"💸 Bill Split - {receipt['store_name']}\n"
        message += f"📅 {receipt['date']} | 📂 {receipt['category']}\n"
        message += f"💰 Total: {receipt['currency']}{receipt['total_amount']}\n\n"
        message += f"👥 Split among {len(splits)} people:\n"
        
        for split in splits:
            message += f"• {split['name']}: {receipt['currency']}{split['amount']:.2f}\n"
        
        message += f"\n🧾 Generated by Receipt Processing System"
        return message
    
    def generate_upi_link(self, amount: float, contact: Dict[str, Any], receipt_info: Dict[str, Any]) -> str:
        """Generate UPI payment link for a specific amount and contact"""
        if not self.upi_details["payee_vpa"] or not self.upi_details["payee_name"]:
            return ""
        
        # Generate transaction reference
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        transaction_ref = f"BILLSPLIT_{timestamp}_{contact['name'].replace(' ', '')}"
        
        # Transaction note
        store_name = receipt_info.get('store_name', 'Unknown Store')
        transaction_note = f"Bill split - {store_name}"
        
        # Format amount to 2 decimal places
        formatted_amount = f"{amount:.2f}"
        
        # Generate UPI deep link
        # Format: upi://pay?pa={payee_address}&pn={payee_name}&am={amount}&tr={transaction_ref}&tn={transaction_note}&cu=INR
        upi_link = (f"upi://pay?"
                   f"pa={urllib.parse.quote(self.upi_details['payee_vpa'])}&"
                   f"pn={urllib.parse.quote(self.upi_details['payee_name'])}&"
                   f"am={formatted_amount}&"
                   f"tr={urllib.parse.quote(transaction_ref)}&"
                   f"tn={urllib.parse.quote(transaction_note)}&"
                   f"cu=INR")
        
        return upi_link
    
    def share_upi_via_whatsapp(self, contact: Dict[str, Any], upi_link: str, amount: float, currency: str, store_name: str):
        """Share UPI payment link via WhatsApp"""
        if not contact['phone'].startswith('+91'):
            print(f"⚠️ {contact['name']}'s phone number might not be in correct format for WhatsApp")
        
        # Remove country code prefix and any non-digits for WhatsApp format
        phone = contact['phone'].replace('+', '').replace('-', '').replace(' ', '')
        
        # Create WhatsApp message with better UPI link formatting
        message = (f"Hi {contact['name']}! 👋\n\n"
                  f"Here's your share from our bill at {store_name}:\n"
                  f"💰 Amount: {currency}{amount:.2f}\n\n"
                  f"💳 *Pay via UPI:*\n"
                  f"{upi_link}\n\n"
                  f"📱 *How to pay:*\n"
                  f"1. Tap the link above OR\n"
                  f"2. Copy the link and open any UPI app\n"
                  f"3. The payment details will auto-fill\n\n"
                  f"Thanks! 😊\n\n"
                  f"🧾 _Sent via Receipt Processing System_")
        
        # Generate WhatsApp URL
        whatsapp_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
        
        try:
            webbrowser.open(whatsapp_url)
            print(f"✅ Opening WhatsApp for {contact['name']} ({contact['phone']})")
            return True
        except Exception as e:
            print(f"❌ Failed to open WhatsApp: {e}")
            return False
    
    def share_upi_via_sms(self, contact: Dict[str, Any], upi_link: str, amount: float, currency: str, store_name: str):
        """Share UPI payment link via SMS"""
        # Create SMS message
        message = (f"Hi {contact['name']}! Your share from {store_name}: "
                  f"{currency}{amount:.2f}. "
                  f"Pay via UPI: {upi_link}")
        
        # Generate SMS URL (works on mobile devices)
        sms_url = f"sms:{contact['phone']}?body={urllib.parse.quote(message)}"
        
        try:
            webbrowser.open(sms_url)
            print(f"✅ Opening SMS for {contact['name']} ({contact['phone']})")
            return True
        except Exception as e:
            print(f"❌ Failed to open SMS: {e}")
            return False
    
    def handle_upi_sharing(self, split_data: Dict[str, Any]):
        """Handle UPI payment link generation and sharing"""
        if not split_data:
            print("❌ No split data available")
            return
        
        receipt_info = split_data["receipt_info"]
        splits = split_data["split_details"]["splits"]
        
        print("\n" + "=" * 60)
        print("💳 UPI PAYMENT REQUEST GENERATION")
        print("=" * 60)
        print(f"💳 Using UPI ID: {self.upi_details['payee_name']} ({self.upi_details['payee_vpa']})")
        
        # Generate UPI links for each person (excluding "You")
        upi_requests = []
        for split in splits:
            if split['name'] != "You":  # Don't generate payment request for yourself
                upi_link = self.generate_upi_link(split['amount'], split, receipt_info)
                if upi_link:
                    upi_requests.append({
                        'contact': split,
                        'upi_link': upi_link,
                        'amount': split['amount'],
                        'currency': split['currency']
                    })
        
        if not upi_requests:
            print("❌ No UPI payment requests to generate")
            return
        
        # Display generated UPI links
        print(f"\n📱 Generated {len(upi_requests)} UPI payment requests:")
        for i, req in enumerate(upi_requests, 1):
            contact = req['contact']
            print(f"\n{i}. {contact['name']} - {req['currency']}{req['amount']:.2f}")
            print(f"   📱 {contact['phone']}")
            print(f"   🔗 {req['upi_link'][:50]}...")
        
        # Ask how to share
        print(f"\n🚀 How would you like to share these payment requests?")
        print("1. 📱 Share all via WhatsApp")
        print("2. 💬 Share all via SMS") 
        print("3. 🎯 Share individually (choose for each person)")
        print("4. 📋 Just show the links (copy manually)")
        print("5. ⏭️ Skip sharing")
        
        while True:
            choice = input("\nChoose option (1-5): ").strip()
            
            if choice == '1':  # WhatsApp all
                print(f"🚀 Opening WhatsApp for {len(upi_requests)} contacts...")
                for i, req in enumerate(upi_requests, 1):
                    contact = req['contact']
                    print(f"\n📱 {i}/{len(upi_requests)} Opening WhatsApp for {contact['name']}...")
                    
                    success = self.share_upi_via_whatsapp(
                        req['contact'], req['upi_link'], 
                        req['amount'], req['currency'], 
                        receipt_info['store_name']
                    )
                    
                    if success and i < len(upi_requests):  # Don't wait after the last one
                        print(f"⏳ Waiting 3 seconds before next contact...")
                        time.sleep(3)
                
                print(f"\n✅ Opened WhatsApp for all {len(upi_requests)} contacts!")
                break
                
            elif choice == '2':  # SMS all
                print(f"🚀 Opening SMS for {len(upi_requests)} contacts...")
                for i, req in enumerate(upi_requests, 1):
                    contact = req['contact']
                    print(f"\n💬 {i}/{len(upi_requests)} Opening SMS for {contact['name']}...")
                    
                    success = self.share_upi_via_sms(
                        req['contact'], req['upi_link'], 
                        req['amount'], req['currency'], 
                        receipt_info['store_name']
                    )
                    
                    if success and i < len(upi_requests):  # Don't wait after the last one
                        print(f"⏳ Waiting 3 seconds before next contact...")
                        time.sleep(3)
                
                print(f"\n✅ Opened SMS for all {len(upi_requests)} contacts!")
                break
                
            elif choice == '3':  # Individual
                for req in upi_requests:
                    contact = req['contact']
                    print(f"\n👤 {contact['name']} - {req['currency']}{req['amount']:.2f}")
                    share_choice = input("Share via: (w)hatsapp, (s)ms, or (skip): ").strip().lower()
                    
                    if share_choice in ['w', 'whatsapp']:
                        self.share_upi_via_whatsapp(
                            req['contact'], req['upi_link'], 
                            req['amount'], req['currency'], 
                            receipt_info['store_name']
                        )
                    elif share_choice in ['s', 'sms']:
                        self.share_upi_via_sms(
                            req['contact'], req['upi_link'], 
                            req['amount'], req['currency'], 
                            receipt_info['store_name']
                        )
                    else:
                        print(f"⏭️ Skipped {contact['name']}")
                break
                
            elif choice == '4':  # Show links
                print("\n📋 UPI PAYMENT LINKS:")
                print("-" * 60)
                for req in upi_requests:
                    contact = req['contact']
                    print(f"\n👤 {contact['name']} ({req['currency']}{req['amount']:.2f})")
                    print(f"📱 Phone: {contact['phone']}")
                    print(f"🔗 UPI Link: {req['upi_link']}")
                    print("-" * 60)
                print("\n💡 Copy these links and send them manually via your preferred app")
                break
                
            elif choice == '5':  # Skip
                print("⏭️ Skipping UPI sharing")
                break
                
            else:
                print("❌ Invalid choice. Please enter 1-5")
        
        print("\n✅ UPI payment request handling completed!")

    def run_interactive_split(self):
        """Run the interactive bill splitting process"""
        print("🎉 Welcome to Bill Splitter!")
        print("💡 This will help you split bills from your processed receipts")
        
        # Step 1: Select receipt
        print("\n📋 Step 1: Select a receipt to split")
        selected_receipt = self.select_receipt()
        
        if not selected_receipt:
            print("❌ No receipt selected. Exiting.")
            return
        
        # Step 2: Select contacts
        print(f"\n👥 Step 2: Select people to split the bill with")
        selected_contacts = self.select_contacts()
        
        if not selected_contacts:
            print("❌ No contacts selected. Exiting.")
            return
        
        # Step 3: Calculate split
        print(f"\n🧮 Step 3: Calculating split...")
        split_result = self.calculate_split(selected_receipt, selected_contacts)
        
        if not split_result:
            print("❌ Unable to calculate split")
            return
        
        # Step 4: Display results
        self.display_split_summary(split_result)
        
        # Step 5: Handle UPI sharing
        self.handle_upi_sharing(split_result)
        
        # Step 6: Save and share options
        print("\n🎯 What would you like to do?")
        print("1. Save split record")
        print("2. Generate share message")
        print("3. Both")
        print("4. Done")
        
        choice = input("Choose option (1-4): ").strip()
        
        if choice in ['1', '3']:
            self.save_split_record(split_result)
        
        if choice in ['2', '3']:
            share_message = self.generate_share_message(split_result)
            print("\n📱 SHARE MESSAGE:")
            print("-" * 40)
            print(share_message)
            print("-" * 40)
            print("💡 Copy the above message to share with friends!")
        
        print("\n✅ Bill splitting completed! 🎉")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Split bills from processed receipts')
    parser.add_argument('--receipt-file', default='pipeline_receipt.json', 
                       help='Path to receipt data file')
    
    args = parser.parse_args()
    
    try:
        splitter = BillSplitter(args.receipt_file)
        splitter.run_interactive_split()
        
    except KeyboardInterrupt:
        print("\n\n👋 Bill splitting cancelled by user")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 