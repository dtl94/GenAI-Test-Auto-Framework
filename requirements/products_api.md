# Products API

## TCAPI001 - GET all products successfully
- Method: GET
- URL: https://automationexercise.com/api/productsList
- Expected Status: 200
- Expected Response: 200
- Expected Keys in Response JSON:
  - products
  - id
  - name
  - price
  - brand
  - category

## TCAPI002 - POST not allowed on products list
- Method: POST
- URL: https://automationexercise.com/api/productsList
- Payload:
  {
    "name": "New Product",
    "price": "100",
    "brand": "TestBrand"
  }
- Expected Status: 200
- Expected Response: 405

## TCAPI003 - PUT not allowed on products list
- Method: PUT
- URL: https://automationexercise.com/api/productsList
- Payload:
  {
    "name": "Updated Product"
  }
- Expected Status: 200
- Expected Response: 405

## TCAPI004 - DELETE not allowed on products list
- Method: DELETE
- URL: https://automationexercise.com/api/productsList
- Expected Status: 200
- Expected Response: 405

