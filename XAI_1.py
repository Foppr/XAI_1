import pandas as pd
import numpy as np
from bokeh import plotting, layouts, io, transform, palettes
from bokeh.models import CustomJS, Dropdown, ColumnDataSource, FactorRange, GeoJSONDataSource, Range1d, LinearAxis

# packages used in unsuccessful tries to make visualizations on geographical map
# from bokeh.sampledata.sample_geojson import geojson
# import geopandas
# import geodatasets
# import json
# import matplotlib
# import pgeocode
#from shapely.geometry import Polygon

from currency_converter import CurrencyConverter
from pathlib import Path
from datetime import datetime

c = CurrencyConverter(fallback_on_missing_rate=True) # object to convert currencies
io.output_file(filename='Dashboard.html', title="Complete Reference for Dungeons and Dragons 5 - Visual Analytics")


# region pre-processing

# --------------- SALES --------------------------------------------------

path_name = Path('assignment1_data').glob(r'sales*10*')
sales = []
for csv in path_name:
    df = pd.read_csv(csv, encoding='utf-8', sep=',')
    sales.append(df)

# The formats of sales files 6 and 7 (November and December) are different than those in 1-5
# changing column names in files 6 and 7 to fit with the others
for csv in ['assignment1_data/sales_202111.csv', 'assignment1_data/sales_202112.csv']:
    df = pd.read_csv(csv, encoding='utf-8', sep=',')
    df = df.rename(columns={
        'Order Charged Date': 'Transaction Date',
        'Product ID': 'Product id',
        'SKU ID': 'Sku Id',
        'Country of Buyer': 'Buyer Country',
        'Postal Code of Buyer': 'Buyer Postal Code',
    })

    # change format of date to fit with other months
    df['Transaction Date'] = df['Transaction Date'].apply(lambda x: datetime.strptime(f"{x}", "%Y-%m-%d"))
    df['Transaction Date'] = df['Transaction Date'].apply(lambda x: x.strftime("%b %d, %Y"))
    # Note: the 67 dates say Nov 01 now while the 1-5 say Nov 1, but it does not impact results

    # There are some charged amounts that are strings and that contain a comma, removing comma and converting to float
    df['Charged Amount'] = df['Charged Amount'].apply(
        lambda x: float(x.replace(',', '')) if isinstance(x, str) else float(x))

    # Charged amounts in Nov and Dec are in original currency. Convert to EUR
    converted_amounts = []
    for i, row in df.iterrows():
        dt = datetime.strptime(row['Transaction Date'], "%b %d, %Y")
        # try to convert using the conversion rate from the transaction date (from the data in currency_converter library)
        try:
            amount = c.convert(row['Charged Amount'], row['Currency of Sale'], 'EUR', date=dt)
            converted_amounts.append(amount)
        # for currencies not available in currency_converter, manually check average conversion rate of transaction month
        except:
            if row['Currency of Sale'] == 'GHS':
                amount = row['Charged Amount'] * 0.1432
            elif row['Currency of Sale'] == 'COP':
                amount = row['Charged Amount'] * 0.0002249
            elif row['Currency of Sale'] == 'CRC':
                amount = row['Charged Amount'] * 0.0014
            else:
                amount = 'NaN' # if no conversion is handled, set amount to NaN (should not happen)

            converted_amounts.append(amount)

    df['Amount (Merchant Currency)'] = converted_amounts

    sales.append(df)

sales_db = pd.concat(sales)

# only use charges for com.vansteinengroentjes.apps.ddfive
sales_db = sales_db.rename(columns={'Product id': 'Product_id'})
sales_db = sales_db[(sales_db['Product_id'] == 'com.vansteinengroentjes.apps.ddfive')]


# --------------- STATS CRASHES --------------------------------------------------
# read csv into a pandas dataframe, concatenate all months to a single df
path_name = Path('assignment1_data').glob(r'stats_crashes*')
stats_crashes = []
for csv in path_name:
    df = pd.read_csv(csv, encoding='utf-16', sep=',')
    stats_crashes.append(df)

crashes_db = pd.concat(stats_crashes, ignore_index=True)

# --------------- RATINGS COUNTRY --------------------------------------------------
# read csv into a pandas dataframe, concatenate all months to a single df

path_name = Path('assignment1_data').glob(r'stats_ratings*country*')
ratings_countries = []
for csv in path_name:
    df = pd.read_csv(csv, encoding='utf-16', sep=',')
    ratings_countries.append(df)

ratings_countries_db = pd.concat(ratings_countries, ignore_index=True)

# --------------- RATINGS OVERVIEW --------------------------------------------------
# read csv into a pandas dataframe, concatenate all months to a single df
path_name = Path('assignment1_data').glob(r'stats_ratings*overview*')
ratings_overview = []
for csv in path_name:
    df = pd.read_csv(csv, encoding='utf-16', sep=',')
    ratings_overview.append(df)

ratings_overview_db = pd.concat(ratings_overview, ignore_index=True)

# endregion pre-processing

# region data collecting

# --------------- Collect data for plots --------------------------------------------------
# Sales
# initialize lists and dictionaries used for sales graphs
days = []
months = []
sku_ids = []
daily_merchant_amount = {}
daily_transaction_count = {}
monthly_merchant_amount = {}
monthly_transaction_count = {}
total_monthly_sales = {}
sku_id_per_month_amount = {}
sku_id_per_month_count = {}

# iterate through all rows of sales db (all transactions)
for i, row in sales_db.iterrows():
    country = row['Buyer Country']
    date = row['Transaction Date']

    # get total revenue and transaction count per day
    if date not in days:
        days.append(date)
        daily_merchant_amount[date] = float(row['Amount (Merchant Currency)'])
        daily_transaction_count[date] = 1
    else:
        daily_merchant_amount[date] += float(row['Amount (Merchant Currency)'])
        daily_transaction_count[date] += 1

    # get total revenue and transaction count per month
    if date[:3] not in months:
        months.append(date[:3])
        month_no = months.index(date[:3])  # 0 for jun, 1 for jul, etc.

        monthly_merchant_amount[date[:3]] = float(row['Amount (Merchant Currency)'])
        monthly_transaction_count[date[:3]] = 1

        # Add to total_monthly_sales
        if country not in total_monthly_sales:
            total_monthly_sales[country] = [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]]
            # [total_sales, total_transaction_count, total_sale per transaction count]
            total_monthly_sales[country][month_no][0] = float(row['Amount (Merchant Currency)'])
            total_monthly_sales[country][month_no][1] = 1
        else:
            total_monthly_sales[country][month_no][0] += float(row['Amount (Merchant Currency)'])
            total_monthly_sales[country][month_no][1] += 1

        total_monthly_sales[country][month_no][2] = total_monthly_sales[country][month_no][0] / \
                                                    total_monthly_sales[country][month_no][1]

        # Sku IDs
        # get the total sales for each sku id per month
        sku_id = row['Sku Id']
        for sku_dict in [sku_id_per_month_amount, sku_id_per_month_count]:
            for sku_id_list in sku_dict.values():
                while len(sku_id_list) != len(months):
                    sku_id_list.append(0)
        if sku_id not in sku_id_per_month_amount:
            sku_id_per_month_amount[sku_id] = [float(row['Amount (Merchant Currency)'])]
            sku_id_per_month_count[sku_id] = [1]
            sku_ids.append(sku_id)
        else:
            sku_id_per_month_amount[sku_id][-1] += float(row['Amount (Merchant Currency)'])
            sku_id_per_month_count[sku_id][-1] += 1

    else:
        monthly_merchant_amount[date[:3]] += float(row['Amount (Merchant Currency)'])
        monthly_transaction_count[date[:3]] += 1

        # Add to total_monthly_sales
        if country not in total_monthly_sales:
            total_monthly_sales[country] = [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]]
            # [total_sales, total_transaction_count, total_sale per transaction count]
            total_monthly_sales[country][month_no][0] = float(row['Amount (Merchant Currency)'])
            total_monthly_sales[country][month_no][1] = 1
        else:
            total_monthly_sales[country][month_no][0] += float(row['Amount (Merchant Currency)'])
            total_monthly_sales[country][month_no][1] += 1

        total_monthly_sales[country][month_no][2] = total_monthly_sales[country][month_no][0] / \
                                                    total_monthly_sales[country][month_no][1]

        # Sku IDs
        # get the total sales for each sku id per month
        sku_id = row['Sku Id']
        if sku_id not in sku_id_per_month_amount:
            sku_id_per_month_amount[sku_id] = [float(row['Amount (Merchant Currency)'])]
            sku_id_per_month_count[sku_id] = [1]
            sku_ids.append(sku_id)
        else:
            sku_id_per_month_amount[sku_id][-1] += float(row['Amount (Merchant Currency)'])
            sku_id_per_month_count[sku_id][-1] += 1

# endregion data collecting


# region dashboard
x = months

# monthly sales
y = list(monthly_merchant_amount.values())
p1 = plotting.figure(x_range=x, title='Monthly Sales', toolbar_location=None, tools="hover", tooltips="@x: $y")
p1.vbar(x, top=y, width=0.5)

# monthly transaction counts
p2 = plotting.figure(x_range=x, title='Monthly Transaction Counts', toolbar_location=None, tools="hover", tooltips="@x: $y")
y = list(monthly_transaction_count.values())
p2.vbar(x, top=y, width=0.5)

x = days

# daily sales
p3 = plotting.figure(x_range=x, title='Daily Sales', toolbar_location=None, tools="hover", tooltips="@x: $y")
y = list(daily_merchant_amount.values())
p3.line(x, y)

# daily transaction counts
p4 = plotting.figure(x_range=x, title='Daily Transaction Counts', toolbar_location=None, tools="hover", tooltips="@x: $y")
y = list(daily_transaction_count.values())
p4.line(x, y)

# Sales volume by Sku ID
data_amount = {"months": months}
for key, value in sku_id_per_month_amount.items():
    data_amount[key] = value

data_count = {"months": months}
for key, value in sku_id_per_month_count.items():
    data_count[key] = value

# plot monthly sales for each sku id
source = ColumnDataSource(data=data_amount)

p1sku = plotting.figure(x_range=months, title="Monthly Sales by Sku Id",
                        height=350, toolbar_location=None, tools="hover", tooltips="@months: $y")

p1sku.vbar(x=transform.dodge('months', -0.25, range=p1sku.x_range), top='unlockcharactermanager', source=source,
           width=0.2, color="#c9d9d3", legend_label="unlockcharactermanager")

p1sku.vbar(x=transform.dodge('months', 0.0, range=p1sku.x_range), top='premium', source=source,
           width=0.2, color="#718dbf", legend_label="premium")

p1sku.x_range.range_padding = 0.1
p1sku.xgrid.grid_line_color = None
p1sku.legend.location = "top_left"
p1sku.legend.orientation = "horizontal"

# plot monthly transaction counts for each sku id
source = ColumnDataSource(data=data_count)

p2sku = plotting.figure(x_range=months, title="Monthly Transaction Counts by Sku Id",
                        height=350, toolbar_location=None, tools="hover", tooltips="@months: $y")

p2sku.vbar(x=transform.dodge('months', -0.25, range=p2sku.x_range), top='unlockcharactermanager', source=source,
           width=0.2, color="#c9d9d3", legend_label="unlockcharactermanager")

p2sku.vbar(x=transform.dodge('months', 0.0, range=p2sku.x_range), top='premium', source=source,
           width=0.2, color="#718dbf", legend_label="premium")

p2sku.x_range.range_padding = 0.1
p2sku.xgrid.grid_line_color = None
p2sku.legend.location = "top_left"
p2sku.legend.orientation = "horizontal"


# Sales volume by country
relevant_countries = ['GB', 'NL', 'AU', 'CA', 'DE'] # chose relevant countries as countries that have enough data

transaction_counts = {'months': months}
sales_by_transaction_count = {'months': months}
for country in relevant_countries:
    transaction_counts[country] = [sales[1] for sales in total_monthly_sales[country]]
    sales_by_transaction_count[country] = [sales[2] for sales in total_monthly_sales[country]]

x = [(country, month) for country in relevant_countries for month in months]
counts = ((transaction_counts['GB']) +
          (transaction_counts['NL']) +
          (transaction_counts['AU']) +
          (transaction_counts['CA']) +
          (transaction_counts['DE']))

sales_by_count = ((sales_by_transaction_count['GB']) +
                  (sales_by_transaction_count['NL']) +
                  (sales_by_transaction_count['AU']) +
                  (sales_by_transaction_count['CA']) +
                  (sales_by_transaction_count['DE']))

source_counts = ColumnDataSource(data=dict(x=x, counts=counts))
source_sales_by_count = ColumnDataSource(data=dict(x=x, counts=sales_by_count))

# plot monthly transaction counts and monthly average revenue per transaction by country
pcountries = plotting.figure(x_range=FactorRange(*x), height=500, title="Monthly transaction counts by country",
                             toolbar_location=None, tools="hover", tooltips="@x: $y")
pcountries_salesbycount = plotting.figure(x_range=FactorRange(*x), height=500, title="Monthly average revenue per transaction",
                             toolbar_location=None, tools="hover", tooltips="@x: $y")

pcountries.vbar(x='x', top='counts', width=0.9, source=source_counts)
pcountries_salesbycount.vbar(x='x', top='counts', width=0.9, source=source_sales_by_count)

pcountries.y_range.start = 0
pcountries.x_range.range_padding = 0.1
pcountries.xaxis.major_label_orientation = 1
pcountries.xgrid.grid_line_color = None

pcountries_salesbycount.y_range.start = 0
pcountries_salesbycount.x_range.range_padding = 0.1
pcountries_salesbycount.xaxis.major_label_orientation = 1
pcountries_salesbycount.xgrid.grid_line_color = None

# crashes:

crashes_list = []
ratings_list = []
daily_ratings = {}
daily_crashes = {}
for i, row in ratings_overview_db.iterrows():
    # format date like Jun 01, 2021
    date = datetime.strptime(row['Date'], "%Y-%m-%d")
    date = date.strftime("%b %d, %Y")

    # get daily crashes and daily reviews
    if date not in daily_crashes:
        daily_crashes[date] = 0
    daily_crashes[date] += float(crashes_db.iloc[i]["Daily Crashes"])

    r = row["Daily Average Rating"]
    # handle missing values
    if pd.isna(r):
        r = float('nan')
    else:
        r = float(r)
    if date not in daily_ratings:
        daily_ratings[date] = 0
    daily_ratings[date] += r

    # get crashes and reviews for reviews by crash scatter plot
    # skip missing values
    if pd.isna(row["Daily Average Rating"]):
        continue
    ratings_list.append(row["Daily Average Rating"])
    crashes_list.append(crashes_db.iloc[i]["Daily Crashes"])

# scatter plot: reviews by crashes
rxc = plotting.figure(title="Daily Average Rating by Daily Crashes")

# points to be plotted
par = np.polyfit(ratings_list, crashes_list, 1, full=True)
slope = par[0][0]
intercept = par[0][1]
y_predicted = [slope * i + intercept for i in ratings_list]

# plotting the graph
rxc.scatter(ratings_list, crashes_list)
# plot regression line
rxc.line(ratings_list, y_predicted, color='red')


# customer satisfaction:
# get all ratings per country
# get amount of negative ratings per country. define negative ratings < 3
ratings_by_country = {}
neg_rating_counts_by_country = {}
for i, row in ratings_countries_db.iterrows():
    country = row['Country']
    if country not in ratings_by_country:
        ratings_by_country[country] = []
    rating =row['Daily Average Rating']
    if pd.isna(rating):
        continue
    rating = float(rating)
    ratings_by_country[country].append(rating)
    if rating < 3:
        if country not in neg_rating_counts_by_country:
            neg_rating_counts_by_country[country] = [0]
        neg_rating_counts_by_country[country][0] += 1

# get average rating per country (sum of all ratings divided by amount of ratings)
avg_rating_by_country = {}
for c in ratings_by_country.keys():
    if len(ratings_by_country[c]) != 0: # handle division by 0
        avg_rating_by_country[c] = sum(ratings_by_country[c]) / len(ratings_by_country[c])



countries = [country for country in avg_rating_by_country.keys()]
print(len(countries), countries)
avg_rating = [rating for rating in avg_rating_by_country.values()]
print(len(avg_rating), avg_rating)
no_ratings = [len(ratings) for ratings in ratings_by_country.values() if len(ratings) != 0]
print(len(no_ratings), no_ratings)

# plot stacked bar plot: amount of ratings on top of average rating (to show relevance of data)
stacks = ['avg_rating', 'no_ratings']

data = {'countries': countries,
        'avg_rating': avg_rating,
        'no_ratings': no_ratings
        }

sorted_x = sorted(countries, key=lambda x: avg_rating[countries.index(x)])

pRatingsAndNumberRatings = plotting.figure(x_range=sorted_x, height=500, title="Average Rating and Number of Ratings per Country",
           toolbar_location=None, tools="hover", tooltips="$name @countries: @$name")

pRatingsAndNumberRatings.vbar_stack(stacks, x='countries', color=('#004488', '#DDAA33'), width=0.9, source=data,
             legend_label=stacks)

pRatingsAndNumberRatings.y_range.start = 0
pRatingsAndNumberRatings.x_range.range_padding = 0.1
pRatingsAndNumberRatings.xgrid.grid_line_color = None
pRatingsAndNumberRatings.axis.minor_tick_line_color = None
pRatingsAndNumberRatings.outline_line_color = None
pRatingsAndNumberRatings.legend.location = "top_left"
pRatingsAndNumberRatings.legend.orientation = "horizontal"


# plot amount of negative ratings per country
x = list(neg_rating_counts_by_country.keys())
pNegRatings = plotting.figure(x_range=x, title='Amount of Ratings lower than 3/5', toolbar_location=None, tools="hover", tooltips="@x: $y")
y = list(neg_rating_counts_by_country.values())
pNegRatings.vbar(x, top=y, width=0.5)


# make line plot for daily average rating and daily crashes
x = list(daily_crashes.keys())
pMonthlyRatings = plotting.figure(x_range=x, title='Daily Average Ratings and Daily Crashes', toolbar_location=None, tools="hover", tooltips="@x: $y")
y = list(daily_crashes.values())
pMonthlyRatings.line(x, y, color='red', legend_label="Crashes")

# make a new y range on the right side for ratings (0-5), otherwise fluctuations in ratings are too small to be visible on graph
x = list(daily_ratings.keys())
pMonthlyRatings.extra_y_ranges = {"ratings": Range1d(start=0, end=5)}
pMonthlyRatings.add_layout(LinearAxis(y_range_name="ratings", axis_label="Rating (0-5)"), 'right')
y = list(daily_ratings.values())
pMonthlyRatings.line(x, y, color='blue', legend_label="Ratings", y_range_name="ratings")

# displaying the model
# make two columns of graphs, fill rows from left to right
graphs = [p1, p2, p3, p4, p1sku, p2sku, rxc, pcountries, pcountries_salesbycount, pRatingsAndNumberRatings, pNegRatings,pMonthlyRatings]
cols = []
row_num = 2
for i in range(0, len(graphs), row_num):
    r = layouts.row(graphs[i: i + row_num])
    cols.append(r)
plotting.show(layouts.column(cols))

# endregion dashboard

# region countries

# failed attempts at getting a visualization of data on a map

# ------------------------------------- COUNTRIES -------------------------------------

# ---------------------------------------------
# world = geopandas.read_file("country_data/ne_110m_admin_0_countries.shp")

# cities = geopandas.read_file(geodatasets.get_path("naturalearth.land"))
# cities = geopandas.read_file("country_data/ne_110m_admin_0_countries.shp")
# cities.plot().figure.canvas.show()
# print(type(cities))
# print(cities.to_string())

#
# import xyzservices.providers as xyz
#
# from bokeh.plotting import figure, show
#
# # range bounds supplied in web mercator coordinates
# p = figure(x_range=(-2000000, 6000000), y_range=(-1000000, 7000000),
#            x_axis_type="mercator", y_axis_type="mercator")
# p.add_tile(xyz.OpenStreetMap.Mapnik)
#
# # show(p)
#
#
# # Example dataset
# df = pd.DataFrame({
#     "country_code": ["FR", "US", "DE"],
#     "value": [0, 0, 0]
# })
#
# # Load built-in world dataset
# world = geopandas.read_file("country_data/ne_110m_admin_0_countries.shp")
#
# # Merge your data with world map (ISO-2 → ISO-3 conversion needed)
# import pycountry
#
# def iso2_to_iso3(code):
#     return pycountry.countries.get(alpha_2=code).alpha_3
#
# df["iso_a3"] = df["country_code"].apply(iso2_to_iso3)
#
# merged = world.merge(df, left_on="ADM0_ISO", right_on="iso_a3")
# print(merged.to_string())
# # Compute country centroids
# merged["center"] = merged.geometry.to_crs('epsg:3785').centroid
# x_axis = merged.center.x
# y_axis = merged.center.y
#
# print(x_axis, y_axis)


# -------- find emerging countries
# find countries with highest sales growth:
# total sales last 2 months divided by total sales first 2 months -1

# endregion countries

# region extra

# tried growth to find emerging countries, no clear trend could be found

# growth = {}
# for i, row in sales_db.iterrows():
#     country = row["Buyer Country"]
#     date = row['Transaction Date']
#     if country not in growth:
#         growth[country] = [0, 0, 0]  # sales first month, sales second month, growth
#
#     if months.index(date[:3]) <= 1:
#         growth[country][0] += float(row['Amount (Merchant Currency)'])
#     elif months.index(date[:3]) >= len(months) - 2:
#         growth[country][1] += float(row['Amount (Merchant Currency)'])
#
# print(growth)
# for country in growth.keys():
#     if growth[country][0] == 0:
#         growth[country][0] = 1
#     growth[country][2] = (growth[country][1] / growth[country][0]) - 1
#
# ranking = sorted(growth.items(), key=lambda x: x[1][2], reverse=True)
#
# for rank, (country, values) in enumerate(ranking, start=1):
#     g = values[2]
#     print(f"{rank}. {country} - Growth: {g:.2f} (Months 1-2 vs 6-7: {values[0]}, {values[1]})")

# endregion extra
