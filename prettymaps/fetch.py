# OpenStreetMap Networkx library to download data from OpenStretMap
from ast import Mult
from operator import ge
import osmnx as ox

# CV2 & Scipy & Numpy & Pandas
import numpy as np

# Shapely
from shapely.geometry import *
from shapely.affinity import *
from shapely.ops import unary_union

# Geopandas
from geopandas import GeoDataFrame

# Matplotlib
from matplotlib.path import Path

# etc
from collections.abc import Iterable
from functools import reduce
from descartes import PolygonPatch

from functools import reduce

# Compute circular or square boundary given point, radius and crs
def get_boundary(point, radius, crs, circle = True, dilate = 0):
    if circle:
        return ox.project_gdf(
            GeoDataFrame(geometry = [Point(point[::-1])], crs = crs)
        ).geometry[0].buffer(radius)
    else:
        x, y = np.stack(ox.project_gdf(
            GeoDataFrame(geometry = [Point(point[::-1])], crs = crs)
        ).geometry[0].xy)
        r = radius
        return Polygon([
            (x-r, y-r), (x+r, y-r), (x+r, y+r), (x-r, y+r)
        ]).buffer(dilate)

# Get perimeter
def get_perimeter(query, by_osmid = False, **kwargs):
    return ox.geocode_to_gdf(query, by_osmid = by_osmid, **kwargs, **{x: kwargs[x] for x in ['circle', 'dilate'] if x in kwargs.keys()})

# Get geometries
def get_geometries(perimeter = None, point = None, radius = None, tags = {}, perimeter_tolerance = 0, union = True, circle = True, dilate = 0):

    if perimeter is not None:
        # Boundary defined by polygon (perimeter)
        geometries = ox.geometries_from_polygon(
            unary_union(perimeter.geometry).buffer(perimeter_tolerance) if perimeter_tolerance > 0 else unary_union(perimeter.geometry),
            tags = {tags: True} if type(tags) == str else tags
        )
        perimeter = unary_union(ox.project_gdf(perimeter).geometry)

    elif (point is not None) and (radius is not None):
        # Boundary defined by circle with radius 'radius' around point
        geometries = ox.geometries_from_point(point, dist = radius+dilate, tags = {tags: True} if type(tags) == str else tags)
        perimeter = get_boundary(point, radius, geometries.crs, circle = circle, dilate = dilate)

    # Project GDF
    if len(geometries) > 0:
        geometries = ox.project_gdf(geometries)

    # Intersect with perimeter
    geometries = geometries.intersection(perimeter)

    if union:
        geometries = unary_union(reduce(lambda x,y: x+y, [
            [x] if type(x) == Polygon else list(x)
            for x in geometries if type(x) in [Polygon, MultiPolygon]
        ], []))
    else:
        geometries = MultiPolygon(reduce(lambda x,y: x+y, [
            [x] if type(x) == Polygon else list(x)
            for x in geometries if type(x) in [Polygon, MultiPolygon]
        ], []))

    return geometries

# Get streets
def get_streets(perimeter = None, point = None, radius = None, layer = 'streets', width = 6, custom_filter = None, circle = True, dilate = 0):

    if layer == 'streets':
        layer = 'highway'

    # Boundary defined by polygon (perimeter)
    if perimeter is not None:
        # Fetch streets data, project & convert to GDF
        streets = ox.graph_from_polygon(unary_union(perimeter.geometry), custom_filter = custom_filter)
        streets = ox.project_graph(streets)
        streets = ox.graph_to_gdfs(streets, nodes = False)
    # Boundary defined by polygon (perimeter)
    elif (point is not None) and (radius is not None):
        # Fetch streets data, save CRS & project
        streets = ox.graph_from_point(point, dist = radius+dilate, custom_filter = custom_filter)
        crs = ox.graph_to_gdfs(streets, nodes = False).crs
        streets = ox.project_graph(streets)
        # Compute perimeter from point & CRS
        perimeter = get_boundary(point, radius, crs, circle = circle, dilate = dilate)
        # Convert to GDF
        streets = ox.graph_to_gdfs(streets, nodes = False)
        # Intersect with perimeter & filter empty elements
        streets.geometry = streets.geometry.intersection(perimeter)
        streets = streets[~streets.geometry.is_empty]

    if type(width) == dict:
        streets = unary_union([
            # Dilate streets of each highway type == 'highway' using width 'w'
            MultiLineString(
                streets[(streets[layer] == highway) & (streets.geometry.type == 'LineString')].geometry.tolist() +
                list(reduce(lambda x, y: x+y, [
                    list(lines)
                    for lines in streets[(streets[layer] == highway) & (streets.geometry.type == 'MultiLineString')].geometry
                ], []))
            ).buffer(w)
            for highway, w in width.items()
        ])
    else:
        # Dilate all streets by same amount 'width'
        streets = MultiLineString(streets.geometry.tolist()).buffer(width)

    return streets

# Get any layer
def get_layer(layer, **kwargs):
    # Fetch perimeter
    if layer == 'perimeter':
        # If perimeter is already provided:
        if 'perimeter' in kwargs:
            return unary_union(ox.project_gdf(kwargs['perimeter']).geometry)
        # If point and radius are provided:
        elif 'point' in kwargs and 'radius' in kwargs:
            # Dummy request to fetch CRS
            crs = ox.graph_to_gdfs(ox.graph_from_point(kwargs['point'], dist = kwargs['radius']), nodes = False).crs
            perimeter = get_boundary(
                kwargs['point'], kwargs['radius'], crs,
                **{x: kwargs[x] for x in ['circle', 'dilate'] if x in kwargs.keys()}
            )
            return perimeter
        else:
            raise Exception("Either 'perimeter' or 'point' & 'radius' must be provided")
    # Fetch streets or railway
    if layer in ['streets', 'railway', 'waterway']:
        return get_streets(**kwargs, layer = layer)
    # Fetch geometries
    else:
        return get_geometries(**kwargs)