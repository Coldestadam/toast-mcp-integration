import httpx
import datetime
import pandas as pd
import logging

# Importing util functions
from utils.client_utils import get_menus_df, get_orders_df

class ToastAPIClient:
    def __init__(self, base_url, client_id, client_secret, restaurant_guid):
        # Necessary API information
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.restaurant_guid = restaurant_guid

        # Token management
        self.token = None
        self.token_expires_at = None

        # Attribute to save dataframe of menus_df that will loaded with get_menu() and be used in get_orders()
        self.menus_df = None

    async def authenticate(self):
        """
        Authenticate the client with the Toast API and obtain an OAuth2 access token.

        This method manages token lifecycle automatically:
        - If a valid token is already cached and not expired, it is returned.
        - Otherwise, a new token is requested from the Toast authentication endpoint
          using the client credentials.

        The token and its expiration time are stored on the client instance for reuse
        in subsequent API calls. A 60-second buffer is applied to the expiration time
        to account for network latency and ensure the token does not expire mid-request.

        Returns:
            str: The active OAuth2 access token.

        Raises:
            ValueError: If the authentication request fails (non-200 response).
            httpx.RequestError: If there is a network-related error during the request.

        Example:
            >>> client = ToastAPIClient(base_url, client_id, client_secret)
            >>> token = await client.authenticate()
            >>> print(token)  # Use this token in subsequent API requests
        """

        # If token is still valid, return it
        if self.token and self.token_expires_at and self.token_expires_at > datetime.datetime.now():
            return self.token

        # Otherwise, fetch a new token
        auth_endpoint = f"https://{self.base_url}/authentication/v1/authentication/login"
        
        # Create request body to get a new token
        request_body = {"clientId":self.client_id,
                        "clientSecret":self.client_secret,
                        "userAccessType": "TOAST_MACHINE_CLIENT"}
        
        # Make the authentication request
        response = httpx.post(auth_endpoint, json=request_body)

        # Raise an error if the request failed
        if not response.status_code == 200:
            raise ValueError("Authentication failed", response.status_code, response.text)
        
        # Parse the response and store the token and its expiration time (in seconds)
        auth_data = response.json()
        self.token = auth_data["token"]['accessToken']
        experation_seconds = auth_data["token"]['expiresIn']

        # Set the token expiration time to the exact time it will expire, since we cannot refresh the expiration time ourselves
        self.token_expires_at = datetime.datetime.now() + datetime.timedelta(seconds=experation_seconds-60) # ToastAPI allows a 60 second buffer

        return self.token
    
    async def get_menus(self) -> pd.DataFrame|None:
        """
        Retrieve all menu items across restaurants from the Toast API and return them
        as a structured Pandas DataFrame.

        This method queries the ToastTab Menus endpoint and delegates the transformation
        of the raw API response into a DataFrame to the helper function `get_menus_df`.
        The resulting DataFrame includes item-level details along with their associated
        restaurant and item group information. The DataFrame is also stored in the
        `menu` attribute of the client instance for reuse in downstream methods such as
        `get_orders`.

        The business owner has configured each menu object to be unique per restaurant,
        with the menu name set to the restaurant name. This allows the method to map
        items to their respective restaurants.

        Returns:
            pandas.DataFrame | None: A DataFrame containing menu details, including item GUIDs,
            item group GUIDs, item names, item groups, restaurant name, and item price.
            Returns None if the request fails.

        Raises:
            ValueError: If the API request fails or returns invalid data.
            httpx.RequestError: If there is a network-related error during the request.

        Link to API documentation:
            https://doc.toasttab.com/openapi/menus/operation/menusGet/
        """

        # Reauthenticate token of client if it has expired
        try:
            token = await self.authenticate()
        except Exception as e:
            logging.info(f"Authentication failed while fetching menus: {e}")
            return None

        menus_endpoint = f"https://{self.base_url}/menus/v2/menus"

        try:
            headers = {"Authorization": f"Bearer {token}",
                       "Toast-Restaurant-External-ID": self.restaurant_guid}

            # Send a GET Request to get all menus
            response = httpx.get(menus_endpoint, headers=headers)

            # Extract a dataframe from menus
            menus_df = get_menus_df(response)

            # Set client's menus_df attribute to menus_df
            self.menus_df = menus_df

            return self.menus_df
        
        except httpx.HTTPError as e:
            logging.info(f"An error occurred while fetching orders: {e}")
            return None

    async def get_orders(self, startDate: str, endDate: str, page_size: int = 100) -> pd.DataFrame|None:
        """
        Retrieve all orders from the Toast API within a given date range for a specific restaurant
        and return them as a structured Pandas DataFrame.

        This method queries the ToastTab Orders Bulk Get endpoint and transforms the response
        into a DataFrame containing detailed order and item-level information. The resulting
        DataFrame can be used for downstream analytics such as sales reporting, item popularity,
        and revenue aggregation.

        Args:
            startDate (str): The start date (ISO 8601 format) for filtering orders.
            endDate (str): The end date (ISO 8601 format) for filtering orders.

        Returns:
            pandas.DataFrame: A DataFrame containing order and item-level details, including
            item names, item prices per order, order guid, item group (Ex. Dessert), and 
            the restaurant the item belongs to.

        Raises:
            ValueError: If the API request fails or returns invalid data.
            httpx.RequestError: If there is a network-related error during the request.


        Link to API documentation:
            https://doc.toasttab.com/openapi/orders/operation/ordersBulkGet/
        """
        # Reauthenticate token of client if it has expired
        try:
            token = await self.authenticate()
        except Exception as e:
            logging.info(f"Authentication failed while fetching menus: {e}")
            return None
        
        orders_endpoint = f"https://{self.base_url}/orders/v2/ordersBulk"

        headers = {
            "Authorization": f"Bearer {token}",
            "Toast-Restaurant-External-ID": self.restaurant_guid
        }

        # Initialize a list to collect all orders across multiple pages
        all_orders = []
        # Start with the first page of results
        page = 1

        try:
            while True:
                # Define query parameters for the API request, including pagination
                params = {
                    "startDate": startDate,   # Start date filter for orders
                    "endDate": endDate,       # End date filter for orders
                    "page": page,             # Current page number
                    "pageSize": page_size     # Number of results per page
                }

                # Send GET request to the Toast Orders API with authentication headers and query params
                response = httpx.get(orders_endpoint, headers=headers, params=params)

                # If the request fails, raise an error with details
                if response.status_code != 200:
                    raise ValueError(f"Failed to fetch orders: {response.status_code}, {response.text}")

                # Parse the JSON response into a Python object (list of orders for this page)
                orders_page = response.json()

                # If no orders are returned, stop fetching (end of available data)
                if not orders_page:
                    break

                # Add the current page of orders to the master list
                all_orders.extend(orders_page)

                # If fewer results than the page size are returned, it means this is the last page
                if len(orders_page) < page_size:
                    break

                # Otherwise, increment the page number and continue fetching
                page += 1

            # After getting all orders, use client's get_menus() method to get menus_df if needed
            if self.menus_df is None:
                menus_df = await self.get_menus()
                if menus_df is None:
                    raise ValueError("Failed to fetch menus, cannot proceed with orders.")
            else:
                menus_df = self.menus_df

            # Convert to DataFrame
            orders_df = get_orders_df(all_orders, menus_df)
            return orders_df

        except httpx.HTTPError as e:
            logging.info(f"An error occurred while fetching orders: {e}")
            return None
