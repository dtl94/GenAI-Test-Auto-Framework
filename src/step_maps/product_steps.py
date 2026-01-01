PRODUCT_STEPS = [
    {
        "pattern": r"add first product to cart",
        "page": "ProductPage",
        "action": "add_first_product"
    },
    {
        "pattern": r"cart badge should show (\d+)",
        "page": "ProductPage",
        "assert": "expect(product_page.cart_badge).to_have_text('{0}')"
    }
]
