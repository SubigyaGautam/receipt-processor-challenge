from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from uuid import uuid4
from typing import List, Dict
import math
import re
from datetime import date, datetime, time


app = FastAPI()

# This will be used to store the data in-memory without persistence
receipts_db: Dict[str, dict] = {}

# Based on the api specification pydantic models are set
# It can be used for data parsing, validation, and serialization, especially in FastAPI 

class Item(BaseModel):
    shortDescription: str 
    price: str

    @validator("shortDescription")
    def validate_short_description(cls, value):

        ''' c.isalnum() : Checks if c is a letter (A-Z, a-z) or a digit (0-9).
            c in " -_"  : Checks if c is a space ( ), hyphen (-), or underscore (_).
            all(...)    : Ensures that every character in value passes at least one of these checks.
            if not ... : Negates the condition, raising an error if any character is not valid
            
            Valid Examples:
                "Valid Name" : Letters & spaces are allowed.
                "Item-123" :  Hyphen allowed.
                "Another_Item" : Underscore allowed.
                
                Invalid Examples:
                "Invalid@Item!" : @ and ! are not allowed.
                "Shop*Name"     : * is not in " -_".
                "123#ABC"       : # is not allowed.
        '''
        if not all(c.isalnum() or c in " -_" for c in value):
            raise ValueError("shortDescription can only contain letters, numbers, spaces, hyphens, and underscores.")
        return value

    @validator("price")
    def validate_price(cls, value):
        try:
            price = float(value)
            if price < 0:
                raise ValueError("Price cannot be negative.")
            if len(value.split(".")[-1]) != 2:
                raise ValueError("Price must have exactly two decimal places.")
        except ValueError:
            raise ValueError("Invalid price format. Expected format: '19.99'.")
        return value

class Receipt(BaseModel):
    retailer: str
    purchaseDate: str  
    purchaseTime: str 
    items: List[Item]
    total: str 


    @validator("retailer")
    def validate_retailer(cls, value):

        ''' c.isalnum() : Checks if c is a letter (A-Z, a-z) or a digit (0-9).
            c in " -&_" : Checks if c is a space ( ), hyphen (-), ampersand (&), or underscore (_).
            all(...)    : Ensures that every character in value passes at least one of these checks.
            if not ...  : Negates the condition, raising an error if any character is not valid.

            Valid Examples:
                "Best Buy"       : Letters & spaces are allowed.
                "Walmart-Super"  : Hyphen allowed.
                "Kroger & Co"    : Ampersand allowed.
                "Shop_Express"   : Underscore allowed.
                
            Invalid Examples:
                "Retailer@123"   : @ is not allowed.
                "Shop*Name"      : * is not in " -&_".
                "Store#1"        : # is not allowed.
        '''
        if not all(c.isalnum() or c in " -&_" for c in value):
            raise ValueError("Retailer name can only contain letters, numbers, spaces, hyphens, and ampersands.")
        return value

    @validator("total")
    def validate_total(cls, value):
        return Item.validate_price(value)  # Reusing the price validation logic


class ReceiptResponse(BaseModel):
    id: str

class PointsResponse(BaseModel):
    points: int

@app.post("/receipts/process", response_model=ReceiptResponse, responses={400: {"description": "The receipt is invalid."}})
def process_receipt(receipt: Receipt):
    if not receipt.retailer or not receipt.items or not receipt.total:
        raise HTTPException(status_code=400, detail="The receipt is invalid.")

    receipt_id = str(uuid4())
    receipts_db[receipt_id] = receipt.dict()
    return {"id": receipt_id}

@app.get("/receipts/{id}/points", response_model=PointsResponse, responses={
    200: {"description": "The number of points awarded."},
    400: {"description": "The receipt is invalid."},
    404: {"description": "No receipt found for that ID."}
})
def get_receipt_points(id: str):
    if id not in receipts_db:
        raise HTTPException(status_code=404, detail="No receipt found for that ID.")

    receipt = receipts_db[id]
    points = calculate_points(receipt)
    return {"points": points}

# Function to calculate points based on given rules
def calculate_points(receipt: dict) -> int:
    points = 0

    # Rule 1: One point for every alphanumeric character in the retailer name
    retailer_name = receipt["retailer"]
    points += sum(c.isalnum() for c in retailer_name)

    # Rule 2: 50 points if the total is a round dollar amount with no cents
    total = float(receipt["total"])
    if total.is_integer():
        points += 50

    # Rule 3: 25 points if the total is a multiple of 0.25
    if total % 0.25 == 0:
        points += 25

    # Rule 4: 5 points for every two items on the receipt
    points += (len(receipt["items"]) // 2) * 5

    # Rule 5: Points for item descriptions that are a multiple of 3
    # If the trimmed length of the item description is a multiple of 3,
    #  multiply the price by `0.2` and round up to the nearest integer. The result is the number of points earned.
    for item in receipt["items"]:
        description = item["shortDescription"].strip()
        price = float(item["price"])
        if len(description) % 3 == 0:
            points += math.ceil(price * 0.2)

    # Rule 6: 6 points if the day in the purchase date is odd
    purchase_date = datetime.strptime(receipt["purchaseDate"], "%Y-%m-%d")
    if purchase_date.day % 2 == 1:
        points += 6

    # Rule 7: 10 points if the time of purchase is after 2:00pm and before 4:00pm
    purchase_time = datetime.strptime(receipt["purchaseTime"], "%H:%M")
    if 14 <= purchase_time.hour < 16:
        points += 10

    return points
