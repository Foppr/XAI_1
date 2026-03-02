import pandas as pd
import numpy as np
import geopandas
import geodatasets
from bokeh import plotting, layouts, io, transform
from bokeh.models import CustomJS, Dropdown, ColumnDataSource, FactorRange, GeoJSONDataSource, Range1d, LinearAxis
# from bokeh.sampledata.sample_geojson import geojson
import json
import matplotlib
# import pgeocode

from shapely.geometry import Polygon

from currency_converter import CurrencyConverter
from pathlib import Path
from datetime import datetime

c = CurrencyConverter(fallback_on_missing_rate=True)
io.output_file('Dashboard.html')

# region pre-processing

# --------------- SALES --------------------------------------------------

path_name = Path('assignment1_data').glob(r'sales*10*')
sales = []
for csv in path_name:
    df = pd.read_csv(csv, encoding='utf-8', sep=',')
    sales.append(df)

# The formats of sales files 6 and 7 are different than those in 1-5
# CHANGE 67 NAMES TO 1-5 NAMES
for csv in ['assignment1_data/sales_202111.csv', 'assignment1_data/sales_202112.csv']:
    df = pd.read_csv(csv, encoding='utf-8', sep=',')
    df = df.rename(columns={
        'Order Charged Date': 'Transaction Date',
        'Product ID': 'Product id',
        'SKU ID': 'Sku Id',
        'Country of Buyer': 'Buyer Country',
        'Postal Code of Buyer': 'Buyer Postal Code',
    })

    # Note: November and December only have Charged Amount, which is in the original currency and not in EUR,
    # (as opposed to the previous months that have Amount (Merchant Currency) In EUR. Converting every Charged Amount
    # to EUR seems infeasible, but we should ask

    # for cell in df['Transaction Date']:
    #     cell = datetime.strptime(f"{cell}", "%Y-%m-%d")
    #     cell = cell.strftime("%b %d, %Y")

    df['Transaction Date'] = df['Transaction Date'].apply(lambda x: datetime.strptime(f"{x}", "%Y-%m-%d"))
    df['Transaction Date'] = df['Transaction Date'].apply(lambda x: x.strftime("%b %d, %Y"))

    df['Charged Amount'] = df['Charged Amount'].apply(
        lambda x: float(x.replace(',', '')) if isinstance(x, str) else float(x))

    # Change currency to EUR
    # df['Amount (Merchant Currency)'] = c.convert(df['Amount (Merchant Currency)'], 'EUR', df['Currency of Sale'], date=df['Transaction Date'])
    converted_amounts = []
    for i, row in df.iterrows():
        dt = datetime.strptime(row['Transaction Date'], "%b %d, %Y")
        try:
            amount = c.convert(row['Charged Amount'], row['Currency of Sale'], 'EUR', date=dt)
            converted_amounts.append(amount)
        except:
            # No data for: GHS and GBP; we took the average conversion rates of November/December
            if row['Currency of Sale'] == 'GHS':
                amount = row['Charged Amount'] * 0.1432
            elif row['Currency of Sale'] == 'COP':
                amount = row['Charged Amount'] * 0.0002249
            elif row['Currency of Sale'] == 'CRC':
                amount = row['Charged Amount'] * 0.0014
            else:
                amount = 'NaN'

            converted_amounts.append(amount)

    df['Amount (Merchant Currency)'] = converted_amounts

    # df['Transaction Date'] = datetime.strptime(f"{df['Transaction Date']}", "%Y-%m-%d")
    # df['Transaction Date'] = df['Transaction Date'].strftime("%b %d, %Y")
    # print(df[:5].to_string())

    # print(df.to_string())

    sales.append(df)

    # Note: the 67 dates say Nov 01 now while the 1-5 say Nov 1, so maybe need to fix this later

# for i, row in sales[-2].iterrows():
#     print(type(row['Amount (Merchant Currency)']))

sales_db = pd.concat(sales)
# print(sales_db[-61:-1].to_string())

# only use charges for com.vansteinengroentjes.apps.ddfive
sales_db = sales_db.rename(columns={'Product id': 'Product_id'})
sales_db = sales_db[(sales_db['Product_id'] == 'com.vansteinengroentjes.apps.ddfive')]
# print(sales_db.to_string())


# --------------- STATS CRASHES --------------------------------------------------
path_name = Path('assignment1_data').glob(r'stats_crashes*')
stats_crashes = []
for csv in path_name:
    df = pd.read_csv(csv, encoding='utf-16', sep=',')
    stats_crashes.append(df)

crashes_db = pd.concat(stats_crashes, ignore_index=True)

# --------------- RATINGS COUNTRY --------------------------------------------------
path_name = Path('assignment1_data').glob(r'stats_ratings*country*')
ratings_countries = []
for csv in path_name:
    df = pd.read_csv(csv, encoding='utf-16', sep=',')
    ratings_countries.append(df)

ratings_countries_db = pd.concat(ratings_countries, ignore_index=True)
# print(ratings_countries_db[:20].to_string())

# --------------- RATINGS OVERVIEW --------------------------------------------------
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

for i, row in sales_db.iterrows():
    country = row['Buyer Country']
    date = row['Transaction Date']

    if date not in days:
        days.append(date)
        daily_merchant_amount[date] = float(row['Amount (Merchant Currency)'])
        daily_transaction_count[date] = 1
    else:
        daily_merchant_amount[date] += float(row['Amount (Merchant Currency)'])
        daily_transaction_count[date] += 1

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
        sku_id = row['Sku Id']
        if sku_id not in sku_id_per_month_amount:
            sku_id_per_month_amount[sku_id] = [float(row['Amount (Merchant Currency)'])]
            sku_id_per_month_count[sku_id] = [1]
            sku_ids.append(sku_id)
        else:
            sku_id_per_month_amount[sku_id][-1] += float(row['Amount (Merchant Currency)'])
            sku_id_per_month_count[sku_id][-1] += 1

# print months
# for date, merchant_amount in monthly_merchant_amount.items():
#     print(date, merchant_amount)
#
# for date, transaction_count in monthly_transaction_count.items():
#     print(date, transaction_count)
#
# for e in total_monthly_sales.items():
#     print(e)

# endregion data collecting

# region dashboard
sales_source = ColumnDataSource(data=sales_db)
x = months

p1 = plotting.figure(x_range=x, title='Monthly Sales')
y = list(monthly_merchant_amount.values())
p1.vbar(x, top=y, width=0.5)

p2 = plotting.figure(x_range=x, title='Monthly Transaction Counts')
y = list(monthly_transaction_count.values())
p2.vbar(x, top=y, width=0.5)

x = days

p3 = plotting.figure(x_range=x, title='Daily Sales')
y = list(daily_merchant_amount.values())
p3.line(x, y)

p4 = plotting.figure(x_range=x, title='Daily Transaction Counts')
y = list(daily_transaction_count.values())
p4.line(x, y)

# Sales volume by Sku ID
data_amount = {"months": months}
for key, value in sku_id_per_month_amount.items():
    data_amount[key] = value

data_count = {"months": months}
for key, value in sku_id_per_month_count.items():
    data_count[key] = value

source = ColumnDataSource(data=data_amount)

p1sku = plotting.figure(x_range=months, title="Monthly Sales by Sku Id",
                        height=350, toolbar_location=None, tools="")

p1sku.vbar(x=transform.dodge('months', -0.25, range=p1sku.x_range), top='unlockcharactermanager', source=source,
           width=0.2, color="#c9d9d3", legend_label="unlockcharactermanager")

p1sku.vbar(x=transform.dodge('months', 0.0, range=p1sku.x_range), top='premium', source=source,
           width=0.2, color="#718dbf", legend_label="premium")

p1sku.x_range.range_padding = 0.1
p1sku.xgrid.grid_line_color = None
p1sku.legend.location = "top_left"
p1sku.legend.orientation = "horizontal"

source = ColumnDataSource(data=data_count)

p2sku = plotting.figure(x_range=months, title="Monthly Transaction Counts by Sku Id",
                        height=350, toolbar_location=None, tools="")

p2sku.vbar(x=transform.dodge('months', -0.25, range=p2sku.x_range), top='unlockcharactermanager', source=source,
           width=0.2, color="#c9d9d3", legend_label="unlockcharactermanager")

p2sku.vbar(x=transform.dodge('months', 0.0, range=p2sku.x_range), top='premium', source=source,
           width=0.2, color="#718dbf", legend_label="premium")

p2sku.x_range.range_padding = 0.1
p2sku.xgrid.grid_line_color = None
p2sku.legend.location = "top_left"
p2sku.legend.orientation = "horizontal"

# Sales volume by country
relevant_countries = ['GB', 'NL', 'AU', 'CA', 'DE']

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

pcountries = plotting.figure(x_range=FactorRange(*x), height=350, title="Monthly transaction counts by country",
                             toolbar_location=None, tools="")
pcountries_salesbycount = plotting.figure(x_range=FactorRange(*x), height=350, title="Monthly average revenue per transaction",
                             toolbar_location=None, tools="")

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

# plotting.show(pcountries)

# crashes_source = ColumnDataSource(data=stats_db)
# ratings_countries_source = ColumnDataSource(data=ratings_countries_db)

# crashes:

crashes_list = []
ratings_list = []
daily_ratings = {}
monthly_crashes = {}
for i, row in ratings_overview_db.iterrows():
    # print(i)
    date = datetime.strptime(row['Date'], "%Y-%m-%d")
    date = date.strftime("%b %d, %Y")
    date_month = date[0:2]

    if date_month not in monthly_crashes:
        monthly_crashes[date_month] = 0
    monthly_crashes[date_month] += float(crashes_db.iloc[i]["Daily Crashes"])

    if pd.isna(row["Daily Average Rating"]):
        continue
    ratings_list.append(row["Daily Average Rating"])
    crashes_list.append(crashes_db.iloc[i]["Daily Crashes"])

    if date not in daily_ratings:
        daily_ratings[date_month] = []
    daily_ratings[date_month].append(float(row["Daily Average Rating"]))

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

avg_rating_by_country = {}
for c in ratings_by_country.keys():
    if len(ratings_by_country[c]) != 0:
        avg_rating_by_country[c] = sum(ratings_by_country[c]) / len(ratings_by_country[c])

x = list(avg_rating_by_country.keys())
y = list(avg_rating_by_country.values())
sorted_x = sorted(x, key=lambda xx: y[x.index(xx)])
pAVGratings = plotting.figure(x_range=sorted_x, title='Average Ratings')
pAVGratings.vbar(x, top=y, width=0.5)

x = list(neg_rating_counts_by_country.keys())
pNegRatings = plotting.figure(x_range=x, title='Amount of Ratings lower than 3/5')
y = list(neg_rating_counts_by_country.values())
pNegRatings.vbar(x, top=y, width=0.5)

avg_monthly_ratings = {}
for m in monthly_ratings.keys():
    if len(monthly_ratings[m]) != 0:
        avg_monthly_ratings[m] = sum(monthly_ratings[m]) / len(monthly_ratings[m])

x = list(monthly_crashes.keys())
pMonthlyRatings = plotting.figure(x_range=x, title='Monthly Ratings and Monthly Crashes')
y = list(monthly_crashes.values())
pMonthlyRatings.line(x, y, color='red', legend_label="Crashes")

x = list(avg_monthly_ratings.keys())
pMonthlyRatings.extra_y_ranges = {"ratings": Range1d(start=0, end=5)}
pMonthlyRatings.add_layout(LinearAxis(y_range_name="ratings", axis_label="Rating (0-5)"), 'right')
y = list(avg_monthly_ratings.values())
pMonthlyRatings.line(x, y, color='blue', legend_label="Ratings", y_range_name="ratings")

# displaying the model
graphs = [p1, p2, p3, p4, p1sku, p2sku, rxc, pcountries, pcountries_salesbycount, pAVGratings, pNegRatings,pMonthlyRatings]
cols = []
row_num = 2
for i in range(0, len(graphs), row_num):
    r = layouts.row(graphs[i: i + row_num])
    cols.append(r)
plotting.show(layouts.column(cols))

# endregion dashboard

# region countries
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
