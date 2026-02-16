// static/js/cart.js
class CartManager {
    constructor() {
        this.initEventListeners();
        this.updateCartCount();
    }

    initEventListeners() {
        // Listen for add to cart buttons
        document.querySelectorAll('.add-to-cart-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const productId = btn.dataset.productId;
                const quantity = btn.dataset.quantity || 1;
                this.addToCart(productId, quantity);
            });
        });

        // Listen for quantity updates on cart page
        document.querySelectorAll('.cart-quantity-input').forEach(input => {
            input.addEventListener('change', (e) => {
                const productId = input.dataset.productId;
                const quantity = parseInt(input.value);
                this.updateCartItem(productId, quantity);
            });
        });

        // Listen for remove buttons
        document.querySelectorAll('.remove-from-cart-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const productId = btn.dataset.productId;
                this.removeFromCart(productId);
            });
        });
    }

    addToCart(productId, quantity = 1) {
        fetch('/orders/ajax/cart/add/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                product_id: productId,
                quantity: quantity
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.showNotification(data.message, 'success');
                this.updateCartCount(data.cart_count);
                this.updateCartTotal(data.cart_total);
                
                // Trigger custom event
                document.dispatchEvent(new CustomEvent('cartUpdated', { 
                    detail: data 
                }));
            } else {
                this.showNotification(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            this.showNotification('Failed to add item to cart', 'error');
        });
    }

    removeFromCart(productId) {
        fetch('/orders/ajax/cart/remove/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                product_id: productId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.showNotification(data.message, 'success');
                this.updateCartCount(data.cart_count);
                this.updateCartTotal(data.cart_total);
                
                // Remove item row if on cart page
                const itemRow = document.querySelector(`.cart-item-${productId}`);
                if (itemRow) {
                    itemRow.remove();
                }
                
                document.dispatchEvent(new CustomEvent('cartUpdated', { 
                    detail: data 
                }));
            } else {
                this.showNotification(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            this.showNotification('Failed to remove item', 'error');
        });
    }

    updateCartItem(productId, quantity) {
        fetch('/orders/ajax/cart/update/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                product_id: productId,
                quantity: quantity
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.updateCartCount(data.cart_count);
                this.updateCartTotal(data.cart_total);
                
                // Update item total
                const itemTotal = document.querySelector(`.item-total-${productId}`);
                if (itemTotal) {
                    itemTotal.textContent = `KSh ${data.item_total.toFixed(2)}`;
                }
                
                document.dispatchEvent(new CustomEvent('cartUpdated', { 
                    detail: data 
                }));
            }
        })
        .catch(error => console.error('Error:', error));
    }

    updateCartCount(count) {
        const cartBadges = document.querySelectorAll('.cart-count');
        cartBadges.forEach(badge => {
            badge.textContent = count;
            if (count > 0) {
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        });
    }

    updateCartTotal(total) {
        const cartTotals = document.querySelectorAll('.cart-total');
        cartTotals.forEach(el => {
            el.textContent = `KSh ${total.toFixed(2)}`;
        });
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 animate-slide-in ${
            type === 'success' ? 'bg-green-500' : 
            type === 'error' ? 'bg-red-500' : 
            'bg-blue-500'
        } text-white`;
        notification.innerHTML = `
            <div class="flex items-center">
                <span class="mr-2">${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
                <span>${message}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
}

// Initialize cart manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.cartManager = new CartManager();
});