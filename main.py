import yaml
import pysftp
import logging
import pandas as pd
import numpy as np
from peloton import get_workouts
import matplotlib.pyplot as plt
import matplotlib.dates as dates
from matplotlib import gridspec

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s', 
    datefmt='%d-%b-%y %H:%M:%S')

with open('config.yaml', 'r') as stream:

    config = yaml.safe_load(stream)

IPADDR = config['address']
USER = config['user']
PRIVKEY = config['private_key']
REMOTEDIR = config['target_folder']
SAMPLERATE = config['sample_rate']
XINTERVAL = config['graph_interval']
TEMPMIN = config['temp_min']
TEMPMAX = config['temp_max']
INCLUDEPTON = config['include_peloton']
TIMEZONE = config['time_zone']
FONTSMALL = 13
FONTMED = 16
FONTLARGE = 24

cnopts = pysftp.CnOpts()

cnopts.hostkeys = None

connection_attempts = 1

logging.info(f'Attempting to establish SFTP connection with {IPADDR}')
# ----------------------------------------------------------------------
# Establish connection with remote server
# ----------------------------------------------------------------------
while True:

    try:

        sftp = pysftp.Connection(
            IPADDR,
            username=USER,
            private_key=PRIVKEY,
            cnopts=cnopts)

        logging.info(f'Attempting to establish SFTP connection with {IPADDR}')

        break

    except Exception as e:

        if connection_attempts <= 10:

            logging.warning(f'Unable to connect to {IPADDR}. Retrying {connection_attempts}/10')
            connection_attempts += 1
        
        else:

            print(e.message)
            exit

sftp.cwd(REMOTEDIR)

data = pd.DataFrame()

for csv in sftp.listdir():

    logging.info(f'Loading {csv} into DataFrame.')

    with sftp.open(csv) as f:

        data = pd.concat(
            [
                data, 
                pd.read_csv(f, parse_dates=['Time'], index_col='Time')
            ]
        )

sftp.close()

data.to_excel('co2-data.xlsx')

# ----------------------------------------------------------------------
# Start Data Plot
# ----------------------------------------------------------------------

# Localize data
data.index = data.index.tz_localize(TIMEZONE)

# Resample data to sample rate
most_recent_timestamp = data.index.max().replace(
    second=0, 
    microsecond=0, 
    minute=0, 
    hour=data.index.max().hour
)

data_window = most_recent_timestamp - np.timedelta64(48, 'h')

data_filter = data.index >= data_window

data_resample = data[data_filter].resample(SAMPLERATE).mean()
data_high = data[data_filter].resample(SAMPLERATE).max()
data_low = data[data_filter].resample(SAMPLERATE).min()

# Set canvas size
fig = plt.figure(figsize=(16, 9), dpi=80)

# Set font size
plt.rc('font', size=FONTSMALL)
plt.rc('axes', titlesize=FONTMED)
plt.rc('axes', labelsize=FONTMED)
plt.rc('xtick', labelsize=FONTSMALL)
plt.rc('ytick', labelsize=FONTSMALL)
plt.rc('legend', fontsize=FONTSMALL)
plt.rc('figure', titlesize=FONTLARGE)

# Set height ratios for subplots
gs = gridspec.GridSpec(2,1,height_ratios=[3,1])

# CO2 PPM Plot
ax0 = plt.subplot(gs[0])

ax0.plot(
    data_resample.index, 
    data_resample['Concentration'], 
    color='g',
    linewidth=3
)

ax0.fill_between(
    data_resample.index, 
    data_low['Concentration'], 
    data_high['Concentration'], 
    alpha=0.2, 
    color='tab:green'
)

# 800 PPM Threshold
ax0.plot(
    data_resample.index, 
    [800 for x in range(len(data_resample.index))],
    color='orange',
    linestyle='--', 
    linewidth=2
)

# 1200 PPM Threshold
ax0.plot(
    data_resample.index, 
    [1200 for x in range(len(data_resample.index))],
    color='red',
    linestyle='-', 
    linewidth=2.5
)

# Y Axis Formatting
ax0.set_ylim(0, np.max([1400, data_resample['Concentration'].max() + 100]))
ax0.yaxis.grid(ls='dotted', lw=1)

# Legend
ax0.legend(
    ['CO$_2$ ppm', '800 ppm thres', '1200 ppm thres'],
    loc='lower left'
)

# Temperature Plot
ax1 = plt.subplot(gs[1])
ax1.plot(
    data_resample.index, 
    data_resample['Temperature'], 
    color='b',
    linewidth=2,
)

# X Axis Formatting
ax0.set_xlim((data_resample.index.min(), data_resample.index.max()))
ax1.set_xlim((data_resample.index.min(), data_resample.index.max()))
ax1.xaxis.set_minor_locator(dates.HourLocator(byhour=range(0, 24, XINTERVAL)))
ax1.xaxis.set_minor_formatter(dates.DateFormatter('%I:%M %p'))
ax0.xaxis.set_major_locator(dates.HourLocator(byhour=(0, 12)))
ax1.xaxis.set_major_locator(dates.HourLocator(byhour=(0, 12)))
ax1.xaxis.set_major_formatter(dates.DateFormatter('%I:%M %p\n%b %d\n%Y'))
ax1.xaxis.grid(True,ls='dotted', lw=1)
plt.setp(ax1.xaxis.get_minorticklabels(), rotation=45)

# Y Axis Formatting
ax0.xaxis.grid(True,ls='dotted', lw=1)
ax1.set_ylim(TEMPMIN, TEMPMAX)
ax1.yaxis.set_ticks(np.linspace(TEMPMIN, TEMPMAX, 5))
ax1.yaxis.grid(True,ls='dotted', lw=1)
yticks = ax1.yaxis.get_major_ticks()
yticks[-1].label1.set_visible(False)

# Remove vertical gap between subplots
plt.subplots_adjust(hspace=.0)

# Highlight off hours
indices = []

for i in range(len(data_resample.index)):

    if (data_resample.index[i].hour >= 18) or (data_resample.index[i].hour < 6):
        
        indices.append(i)

for i in range(len(indices) - 1):

    ax0.axvspan(data_resample.index[indices[i]], 
                data_resample.index[indices[i] + 1], 
                facecolor='darkblue',
                edgecolor='none', 
                alpha=0.1)

    ax1.axvspan(data_resample.index[indices[i]], 
            data_resample.index[indices[i] + 1], 
            facecolor='darkblue',
            edgecolor='none', 
            alpha=0.1)

# Highlight Peloton Activity
if INCLUDEPTON:

    logging.info(f'Fetching Peloton workout data.')
    peloton_data = get_workouts()

    peloton_data_filtered = peloton_data[peloton_data.created_at_clean_localized >= data_window]
    logging.info(f'Overlaying {peloton_data_filtered.shape[0]} workout(s).')

    for i, row in peloton_data_filtered.iterrows():

        peloton_highlight = {
            'xmin':data_resample.index[data_resample.index <= row.created_at_clean_localized].max(),
            'xmax':data_resample.index[data_resample.index >= row.end_time_clean_localized].min(),
            'facecolor':'pink',
            'edgecolor':'none',
            'alpha':0.5
        }

        if np.logical_and(
            np.logical_not(pd.isnull(peloton_highlight['xmin'])),
            np.logical_not(pd.isnull(peloton_highlight['xmax']))):

            ax0.axvspan(**peloton_highlight)
            ax1.axvspan(**peloton_highlight)

# Labels
plt.suptitle('Home Office & Workout Room CO$_2$ Levels',fontsize=24, y=1)
ax0.set_title('Rolling 48 Hour Window / 15 Minute Intervals', fontsize=16)
ax0.set_ylabel('CO$_2$ Concentration (ppm)')
ax1.set_ylabel('Temperature ($^\circ$C)')
ax1.set_xlabel(f'Time\nUpdated: {data.index.max()}')

logging.info(f'Exporting chart.')
fig.savefig('co2-chart.jpg', bbox_inches='tight')