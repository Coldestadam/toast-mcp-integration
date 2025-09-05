import httpx
import pandas as pd
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
