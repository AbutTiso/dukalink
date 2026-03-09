from django import forms
from .models import Product, Category

class ProductForm(forms.ModelForm):
    # Add a field for creating new categories on the fly
    new_category = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Or add new category...'
        })
    )
    
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'stock', 'image', 'is_available', 'category']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Product Description', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Price in Ksh'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Stock Quantity'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order categories alphabetically in dropdown
        self.fields['category'].queryset = Category.objects.all().order_by('name')
        self.fields['category'].empty_label = "Select a category..."
    
    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        new_category = cleaned_data.get('new_category')
        
        # If new_category is provided, create it and use it
        if new_category and not category:
            category_obj, created = Category.objects.get_or_create(
                name=new_category.strip()
            )
            cleaned_data['category'] = category_obj
        
        return cleaned_data