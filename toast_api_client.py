import httpx
import datetime
import os
import pandas as pd

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
        token = await self.authenticate()
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
            print(f"An error occurred while fetching orders: {e}")
            return None

    async def get_orders(self, startDate: str, endDate: str, page_size: int = 100) -> pd.DataFrame:
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
        token = await self.authenticate()
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
            print(f"An error occurred while fetching orders: {e}")
            return pd.DataFrame()
    
def get_menus_df(menus_response: httpx.Response) -> pd.DataFrame:
    """
    Transform a Toast API menus response into a structured Pandas DataFrame.

    This function parses the JSON response returned by the Toast Menus API and
    extracts item-level details along with their associated restaurant and item
    group information. The resulting DataFrame provides a tabular representation
    of menu items across restaurants, suitable for downstream analytics such as
    sales reporting, item popularity, and price analysis.

    Due to a known Toast API bug, some `menuGroups` may contain nested `menuGroups`
    instead of listing all items directly. To address this, the function includes
    an additional parsing step that iterates through these nested groups to ensure
    all items are captured. Without this fix, certain items would be missing from
    the DataFrame.

    Args:
        menus_response (httpx.Response): The HTTP response object returned from
            the Toast Menus API endpoint.

    Returns:
        pandas.DataFrame: A DataFrame containing menu details with the following columns:
            - item_guid (str): Unique identifier for the menu item.
            - item_group_guid (str): Unique identifier for the item group (e.g., Desserts).
            - item_name (str): Name of the menu item.
            - restaurant_name (str): Name of the restaurant (derived from the menu name).
            - item_group_name (str): Name of the item group/category.
            - item_price (float|int): Price of the menu item.

    Example:
        >>> response = httpx.get("https://api.toasttab.com/menus/v2/menus", headers=headers)
        >>> menus_df = get_menus_df(response)
        >>> print(menus_df.head())
          item_guid item_group_guid item_name restaurant_name item_group_name item_price
        0   abc1234         grp5678   Brownie     MyRestaurant        Dessert       3.99
        1   def5678         grp5678     Cake     MyRestaurant        Dessert       4.99
    """
    # Initializing a dictionary to store data to convert to a DataFrame
    columns_dict={"item_guid":[],
                  "item_group_guid":[],
                  "item_name":[],
                  "restaurant_name":[],
                  "item_group_name":[],
                  "item_price":[]}
    
    # Getting json from the menus_response
    menus_json = menus_response.json()
    
    # Looping through each menu that represents a single restaurant
    for menu in menus_json["menus"]:
        # Getting restaurant name from the name of the menu
        restaurant_name = menu["name"]

        # Looping through each item group (ex. Dessert) through each menu
        for item_group in menu["menuGroups"]:

            # Get item_group guid and item_group name
            item_group_guid = item_group["guid"]
            item_group_name = item_group["name"]

            # Looping through each item in item group
            for item in item_group['menuItems']:

                # Get item guid, item name, and item price
                item_guid = item["guid"]
                item_name = item["name"]
                item_price = item["price"]

                # Append values to the columns_dict
                columns_dict["item_guid"].append(item_guid)
                columns_dict["item_group_guid"].append(item_group_guid)
                columns_dict["item_name"].append(item_name)
                columns_dict["restaurant_name"].append(restaurant_name)
                columns_dict["item_group_name"].append(item_group_name)
                columns_dict["item_price"].append(item_price)

            # API Bug Fix for where there are nesting menuGroups in an item_group
            # This is to get the individual items in the nesting menuGroups
            for sub_item_group in item_group["menuGroups"]:
                # Get item_group guid and item_group name
                sub_item_group_guid = sub_item_group["guid"]
                sub_item_group_name = sub_item_group["name"]

                # Looping through each item in item group
                for sub_item in sub_item_group['menuItems']:

                    # Get item guid, item name, and item price
                    sub_item_guid = sub_item["guid"]
                    sub_item_name = sub_item["name"]
                    sub_item_price = sub_item["price"]

                    # Append values to the columns_dict
                    columns_dict["item_guid"].append(sub_item_guid)
                    columns_dict["item_group_guid"].append(sub_item_group_guid)
                    columns_dict["item_name"].append(sub_item_name)
                    columns_dict["restaurant_name"].append(restaurant_name)
                    columns_dict["item_group_name"].append(sub_item_group_name)
                    columns_dict["item_price"].append(sub_item_price)

    menus_df = pd.DataFrame.from_dict(data=columns_dict)
    
    return menus_df

def get_orders_df(all_orders: list[dict], menus_df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform a list of Toast API order objects into a structured Pandas DataFrame.

    This function processes raw order data returned by the Toast Orders API and
    extracts item-level details for all approved (paid) orders. Each order may
    contain multiple checks, and each check may contain multiple item selections.
    The function flattens this nested structure into a tabular format, where each
    row represents a single item purchased in an order.

    To enrich the order data with contextual information, the function performs
    a left join with the provided `menus_df` DataFrame. This adds restaurant-level
    and item group metadata (e.g., restaurant name, item group name) to each order
    item, enabling downstream analytics such as sales reporting, revenue aggregation,
    and item popularity analysis.

    Args:
        all_orders (list[dict]): A list of order objects returned by the Toast Orders API.
            Each order should include approval status, order GUID, paid date, checks,
            and item selections.
        menus_df (pandas.DataFrame): A DataFrame of menu metadata, typically generated
            by `get_menus_df()`. Must include `item_guid` and `item_group_guid` columns
            for joining, along with restaurant and item group details.

    Returns:
        pandas.DataFrame: A DataFrame containing enriched order details with the following columns:
            - item_guid (str): Unique identifier for the menu item.
            - item_group_guid (str): Unique identifier for the item group.
            - item_name (str): Display name of the purchased item.
            - item_price (float|int): Price of the purchased item.
            - order_guid (str): Unique identifier for the order.
            - paid_date (datetime): Timestamp when the order was paid.
            - restaurant_name (str): Name of the restaurant (from `menus_df`).
            - item_group_name (str): Name of the item group/category (from `menus_df`).

    Example:
        >>> orders = [...]  # Retrieved from Toast Orders API
        >>> menus_df = get_menus_df(menus_response)
        >>> orders_df = get_orders_df(orders, menus_df)
        >>> print(orders_df.head())
          item_guid item_group_guid item_name  item_price   order_guid  paid_date  restaurant_name item_group_name
        0   abc1234         grp5678   Brownie        3.99  order_00123 2024-09-01     MyRestaurant        Dessert
        1   def5678         grp5678     Cake        4.99  order_00123 2024-09-01     MyRestaurant        Dessert
    """
    # Initializing a dictionary to store data of all individual orderd items to convert to a DataFrame
    columns_dict={"item_guid":[],
                  "item_group_guid":[],
                  "item_name":[],
                  "item_price":[],
                  "order_guid":[],
                  "paid_date":[]}

    # Looping through each order
    for order in all_orders:

        # Only add orders that have approved; hence they are paid for
        if order["approvalStatus"] == "APPROVED":
            
            # Getting order guid
            order_guid = order["guid"]

            # Getting order paid date
            paid_date = pd.to_datetime(order["paidDate"])

            # Looping through each check in each order; since some orders are split for separate checks
            for check in order["checks"]:

                # Looping through item selection in each check
                for item in check["selections"]:
                    
                    # Getting item name, price, guid, and group guid safely
                    item_name = item.get("displayName")
                    item_price = item.get("price")
                    item_guid = (item.get("item") or {}).get("guid")
                    item_group_guid = (item.get("itemGroup") or {}).get("guid")

                    # Append values to the columns_dict
                    columns_dict["item_guid"].append(item_guid)
                    columns_dict["item_group_guid"].append(item_group_guid)
                    columns_dict["item_name"].append(item_name)
                    columns_dict["item_price"].append(item_price)
                    columns_dict["order_guid"].append(order_guid)
                    columns_dict["paid_date"].append(paid_date)

    # Getting a dataframe from the dict we created
    orders_df = pd.DataFrame.from_dict(data=columns_dict)

    # Dropping item name and item price from menus_df to get only the restaurant name and item group name
    menus_subset_df = menus_df.drop(columns=["item_name", "item_price"])

    # Using menus_df to get restaurant name and item group name, use left join
    joined_orders_df = pd.merge(orders_df,
                                menus_subset_df,
                                on=["item_guid", "item_group_guid"],
                                how="left")

    
    return joined_orders_df
