# orders/cart.py
from products.models import Product

class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get("cart")
        if not cart:
            cart = self.session["cart"] = {}
        self.cart = cart

    def add(self, product, quantity=1):
        product_id = str(product.id)
        if product_id in self.cart:
            self.cart[product_id]["quantity"] += quantity
        else:
            self.cart[product_id] = {
                "name": product.name,
                "price": float(product.price),
                "quantity": quantity,
                "vendor": product.business.name,  # ADD THIS - for vendor name
                "image_url": product.image.url if product.image else None  # ADD THIS - for images
            }
        self.save()

    def remove(self, product):
        product_id = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def clear(self):
        """Clear the cart."""
        # Remove from session
        if "cart" in self.session:
            del self.session["cart"]
            self.session.modified = True
        
        # IMPORTANT: Clear the local cart dictionary
        self.cart = {}  # ← THIS LINE WAS MISSING!
        
        # Force session save
        self.session.save()

    def save(self):
        self.session["cart"] = self.cart
        self.session.modified = True

    def get_total(self):
        return sum(item["price"] * item["quantity"] for item in self.cart.values())

    def items(self):
        return self.cart.items()
    
    def __len__(self):
        """Return the total number of items in cart"""
        return sum(item["quantity"] for item in self.cart.values())
    
    def __iter__(self):
        """Iterate over cart items and fetch products from database for images"""
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        
        # Create a copy of the cart
        cart = self.cart.copy()
        
        # Add product objects to cart items
        for product in products:
            product_id = str(product.id)
            if product_id in cart:
                cart[product_id]['product'] = product
                cart[product_id]['total_price'] = cart[product_id]['price'] * cart[product_id]['quantity']
                # Update image URL from database (in case it changed)
                cart[product_id]['image_url'] = product.image.url if product.image else None
        
        # Yield each item
        for item in cart.values():
            yield item