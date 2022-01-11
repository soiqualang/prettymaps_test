# OpenStreetMap Networkx library to download data from OpenStretMap
import osmnx as ox

# Matplotlib-related stuff, for drawing
from matplotlib.path import Path
from matplotlib import pyplot as plt
from matplotlib.patches import PathPatch

# CV2 & Scipy & Numpy & Pandas
import numpy as np
from numpy.random import choice

# Shapely
from shapely.geometry import *
from shapely.affinity import *

# Geopandas
from geopandas import GeoDataFrame

# etc
import re
import pandas as pd
from functools import reduce
from tabulate import tabulate
from IPython.display import Markdown, display
from collections.abc import Iterable

# Fetch
from .fetch import *

# Helper functions
def get_hash(key):
    return frozenset(key.items()) if type(key) == dict else key

# Drawing functions
def show_palette(palette, description = ''):
    '''
    Helper to display palette in Markdown
    '''

    colorboxes = [
        f'![](https://placehold.it/30x30/{c[1:]}/{c[1:]}?text=)'
        for c in palette
    ]

    display(Markdown((description)))
    display(Markdown(tabulate(pd.DataFrame(colorboxes), showindex = False)))

def get_patch(shape, **kwargs):
    '''
    Convert shapely object to matplotlib patch
    '''
    #if type(shape) == Path:
    #    return patches.PathPatch(shape, **kwargs)
    if type(shape) == Polygon and shape.area > 0:
        return PolygonPatch(list(zip(*shape.exterior.xy)), **kwargs)
    else:
        return None

# Plot a single shape
def plot_shape(shape, ax, vsketch = None, **kwargs):
    '''
    Plot shapely object
    '''
    if isinstance(shape, Iterable) and type(shape) != MultiLineString:
        for shape_ in shape:
            plot_shape(shape_, ax, vsketch = vsketch, **kwargs)
    else:
        if not shape.is_empty:

            if vsketch is None:
                ax.add_patch(PolygonPatch(shape, **kwargs))
            else:
                if ('draw' not in kwargs) or kwargs['draw']:

                    if 'stroke' in kwargs:
                        vsketch.stroke(kwargs['stroke'])
                    else:
                        vsketch.stroke(1)

                    if 'penWidth' in kwargs:
                        vsketch.penWidth(kwargs['penWidth'])
                    else:
                        vsketch.penWidth(0.3)

                    if 'fill' in kwargs:
                        vsketch.fill(kwargs['fill'])
                    else:
                        vsketch.noFill()

                    vsketch.geometry(shape)

# Plot a collection of shapes
def plot_shapes(shapes, ax, vsketch = None, palette = None, **kwargs):
    '''
    Plot collection of shapely objects (optionally, use a color palette)
    '''
    if not isinstance(shapes, Iterable):
        shapes = [shapes]

    for shape in shapes:
        if palette is None:
            plot_shape(shape, ax, vsketch = vsketch, **kwargs)
        else:
            plot_shape(shape, ax, vsketch = vsketch, fc = choice(palette), **kwargs)

# Parse query (by coordinates, OSMId or name)
def parse_query(query):
    if type(query) in([Polygon, MultiPolygon]):
        return 'polygon'
    elif type(query) == tuple:
        return 'coordinates'
    elif re.match('''[A-Z][0-9]+''', query):
        return 'osmid'
    else:
        return 'address'

# Apply transformation (translation & scale) to layers
def transform(layers, x, y, scale_x, scale_y, rotation):
    # Transform layers (translate & scale)
    k, v = zip(*layers.items())
    v = GeometryCollection(v)
    if (x is not None) and (y is not None):
        v = translate(v, *(np.array([x, y]) - np.concatenate(v.centroid.xy)))
    if scale_x is not None:
        v = scale(v, scale_x, 1)
    if scale_y is not None:
        v = scale(v, 1, scale_y)
    if rotation is not None:
        v = rotate(v, rotation)
    layers = dict(zip(k, v))
    return layers

def draw_text(ax, text, x, y, **kwargs):
    ax.text(x, y, text, **kwargs)

# Plot
def plot(
    # Address
    query,
    # Whether to use a backup for the layers
    backup = None,
    # Custom postprocessing function on layers
    postprocessing = None,
    # Radius (in case of circular plot)
    radius = None,
    # Which layers to plot
    layers = {'perimeter': {}},
    # Drawing params for each layer (matplotlib params such as 'fc', 'ec', 'fill', etc.)
    drawing_kwargs = {},
    # OSM Caption parameters
    osm_credit = {},
    # Figure parameters
    figsize = (10, 10), ax = None, title = None,
    # Vsketch parameters
    vsketch = None,
    # Transform (translation & scale) params
    x = None, y = None, scale_x = None, scale_y = None, rotation = None,
    ):

    # Interpret query
    query_mode = parse_query(query)

    # Save maximum dilation for later use
    dilations = [kwargs['dilate'] for kwargs in layers.values() if 'dilate' in kwargs]
    max_dilation = max(dilations) if len(dilations) > 0 else 0

    ####################
    ### Fetch Layers ###
    ####################

    # Use backup if provided
    if backup is not None:
        layers = backup
    # Otherwise, fetch layers
    else:
        # Define base kwargs
        if radius:
            base_kwargs = {
                'point': query if query_mode == 'coordinates' else ox.geocode(query),
                'radius': radius
            }
        else:
            base_kwargs = {
                'perimeter': query if query_mode == 'polygon' else get_perimeter(query, by_osmid = query_mode == 'osmid')
            }

        # Fetch layers
        layers = {
            layer: get_layer(
                layer,
                **base_kwargs,
                **(kwargs if type(kwargs) == dict else {})
            )
            for layer, kwargs in layers.items()
        }

        # Apply transformation to layers (translate & scale)
        layers = transform(layers, x, y, scale_x, scale_y, rotation)

        # Apply postprocessing step to layers
        if postprocessing is not None:
            layers = postprocessing(layers)

    ############
    ### Plot ###
    ############

    # Matplot-specific stuff (only run if vsketch mode isn't activated)
    if vsketch is None:
        # Ajust axis
        ax.axis('off')
        ax.axis('equal')
        ax.autoscale()

    # Plot background
    if 'background' in drawing_kwargs:
        xmin, ymin, xmax, ymax = layers['perimeter'].bounds
        geom = scale(Polygon([
            (xmin, ymin),
            (xmin, ymax),
            (xmax, ymax),
            (xmax, ymin)
        ]), 2, 2)

        if vsketch is None:
            ax.add_patch(PolygonPatch(geom, **drawing_kwargs['background']))
        else:
            vsketch.geometry(geom)
    
    # Adjust bounds
    xmin, ymin, xmax, ymax = layers['perimeter'].buffer(max_dilation).bounds
    dx, dy = xmax-xmin, ymax-ymin
    if vsketch is None:
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)

    # Draw layers
    for layer, shapes in layers.items():
        kwargs = drawing_kwargs[layer] if layer in drawing_kwargs else {}
        if 'hatch_c' in kwargs:
            # Draw hatched shape
            plot_shapes(shapes, ax, vsketch = vsketch, lw = 0, ec = kwargs['hatch_c'], **{k:v for k,v in kwargs.items() if k not in ['lw', 'ec', 'hatch_c']})
            # Draw shape contour only
            plot_shapes(shapes, ax, vsketch = vsketch, fill = False, **{k:v for k,v in kwargs.items() if k not in ['hatch_c', 'hatch', 'fill']})
        else:
            # Draw shape normally
            plot_shapes(shapes, ax, vsketch = vsketch, **kwargs)

    if ((isinstance(osm_credit, dict)) or (osm_credit is True)) and (vsketch is None):
        x, y = figsize
        d = .8*(x**2+y**2)**.5
        draw_text(
            ax,
            (osm_credit['text'] if 'text' in osm_credit else 'data © OpenStreetMap contributors\ngithub.com/marceloprates/prettymaps'),
            x = xmin + (osm_credit['x']*dx if 'x' in osm_credit else 0),
            y = ymax - 4*d - (osm_credit['y']*dy if 'y' in osm_credit else 0),
            fontfamily = (osm_credit['fontfamily'] if 'fontfamily' in osm_credit else 'Ubuntu Mono'),
            fontsize = (osm_credit['fontsize']*d if 'fontsize' in osm_credit else d),
            zorder = (osm_credit['zorder'] if 'zorder' in osm_credit else len(layers)+1),
            **{k:v for k,v in osm_credit.items() if k not in ['x', 'y', 'fontfamily', 'fontsize', 'zorder']}
        )

    # Return perimeter
    return layers
