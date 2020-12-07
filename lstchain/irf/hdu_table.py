import numpy as np
import os
import logging

from lstchain.reco.utils import camera_to_altaz

import astropy.units as u
from astropy.table import Table, Column, vstack, QTable
from astropy.io import fits
from astropy.coordinates import SkyCoord, AltAz
from astropy.time import Time
from ..reco.utils import location


__all__ = [
    'create_obs_hdu_index',
    'create_event_list'
    ]

log = logging.getLogger(__name__)

DEFAULT_HEADER = fits.Header()
DEFAULT_HEADER["HDUDOC"] = "https://github.com/open-gamma-ray-astro/gamma-astro-data-formats"
DEFAULT_HEADER["HDUVERS"] = "0.2"
DEFAULT_HEADER["HDUCLASS"] = "GADF"

def create_obs_hdu_index(filename_list, fits_dir):
    """
    Create the obs table and hdu table (below some explanation)

    A two-level index file scheme is used in the IACT community to allow an arbitrary folder structures
    For each directory tree, two files should be present:
    **obs-index.fits.gz**
    (defined in http://gamma-astro-data-formats.readthedocs.io/en/latest/data_storage/obs_index/index.html)
    **hdu-index.fits.gz**
    (defined in http://gamma-astro-data-formats.readthedocs.io/en/latest/data_storage/hdu_index/index.html)

    obs-index contains the single run informations e.g.
    (OBS_ID, RA_PNT, DEC_PNT, ZEN_PNT, ALT_PNT)
    while hdu-index contains the informations about the locations of the other HDU (header data units)
    necessary to the analysis e.g. A_eff, E_disp and so on...
        http://gamma-astro-data-formats.readthedocs.io/en/latest/

    This function will create the necessary data format, starting from the path that contains the DL3
    converted fits file.

    Parameters
    ----------
    filename_list : list
        list of filenames
    fits_dir : str
        directory containing the fits file
    """

    hdu_tables = []
    obs_tables = []

    #loop through the files
    for file in filename_list:
        filepath = fits_dir/file
        if filepath.is_file():
            try:
                event_table = Table.read(filepath, hdu="EVENTS")
                gti_table = Table.read(filepath, hdu="GTI")
                pointing_table = Table.read(filepath, hdu="POINTING")
            except Exception:
                log.error(f"fits corrupted for file {file}")
                continue
        else:
            log.error(f"fits {file} doesn't exist")
            continue

        #The column names for the table follows the scheme as shown in
        #https://gamma-astro-data-formats.readthedocs.io/en/latest/general/HDU_CLASS.html
        ###############################################
        # Event list
        t_events = Table(
                {
                'OBS_ID':[event_table.meta['OBS_ID']],
                'HDU_TYPE':['events'],
                'HDU_CLASS':['events'],
                'HDU_CLASS2':[''],
                'HDU_CLASS3':[''],
                'HDU_CLASS4':[''],
                'FILE_DIR':[''],
                'FILE_NAME': [file],
                'HDU_NAME':['events']},
                dtype=('>i8', 'S6', 'S10',
                'S20', 'S20', 'S20', 'S70',
                'S54', 'S20')
                )
        hdu_tables.append(t_events)
        ###############################################
        #GTI
        t_gti = t_events.copy()

        t_gti['HDU_TYPE'] = 'gti'
        t_gti['HDU_CLASS'] = 'gti'
        t_gti['HDU_NAME'] = 'gti'

        hdu_tables.append(t_gti)
        ###############################################
        #POINTING
        t_pnt = t_events.copy()

        t_pnt['HDU_TYPE'] = ['pointing']
        t_pnt['HDU_CLASS'] = ['pointing']
        t_pnt['HDU_NAME'] = ['pointing']

        hdu_tables.append(t_pnt)
        ###############################################
        #Energy Dispersion
        try:
            Table.read(filepath, hdu="ENERGY DISPERSION")
            t_edisp = t_events.copy()

            t_edisp['HDU_TYPE'] = ['edisp']
            t_edisp['HDU_CLASS'] = ['edisp_2d']
            t_edisp['HDU_CLASS2'] = ['EDISP']
            t_edisp['HDU_CLASS3'] = ['POINT-LIKE']
            t_edisp['HDU_CLASS4'] = ['EDISP_2D']
            t_edisp['HDU_NAME'] = ['ENERGY DISPERSION']

            hdu_tables.append(t_edisp)
        except:
            log.error('Energy Dispersion HDU not found')
        ###############################################
        #Effective Area
        try:
            Table.read(filepath, hdu="EFFECTIVE AREA")
            t_aeff = t_edisp.copy()
            t_aeff['HDU_TYPE'] = ['aeff']
            t_aeff['HDU_CLASS'] = ['aeff_2d']
            t_aeff['HDU_CLASS2'] = ['AEFF']
            t_aeff['HDU_CLASS4'] = ['AEFF_2D']
            t_aeff['HDU_NAME'] = ['EFFECTIVE AREA']

            hdu_tables.append(t_aeff)
        except:
            log.error('Effective Area HDU not found')
        ###############################################
        # Obs_table
        t_obs = Table(
            {'OBS_ID' : [event_table.meta['OBS_ID']],
            'DATE_OBS' : [event_table.meta['DATE_OBS']],
            'RA_PNT' : [pointing_table.meta['RA_PNT']],
            'DEC_PNT' : [pointing_table.meta['DEC_PNT']],
            'ZEN_PNT' : [90 - float(pointing_table.meta['ALT_PNT'])],
            'ALT_PNT' : [pointing_table.meta['ALT_PNT']],
            'AZ_PNT' : [pointing_table.meta['AZ_PNT']],
            'RA_OBJ' : [event_table.meta['RA_OBJ']],
            'DEC_OBJ' : [event_table.meta['DEC_OBJ']],
            'ONTIME': [event_table.meta["ONTIME"]],
            'LIVETIME' : [event_table.meta["LIVETIME"]],
            'DEADC' : [event_table.meta["DEADC"]],
            'TSTART' : [event_table.meta["TSTART"]],
            'TSTOP' : [event_table.meta["TSTOP"]],
            'OBJECT' : [event_table.meta['OBJECT']],
            'OBS_MODE' : [event_table.meta['OBS_MODE']],
            'N_TELS' : [event_table.meta["N_TELS"]],
            'TELLIST' : [event_table.meta["TELLIST"]]},
            dtype=('>i8', '>S12','>f4', '>f4', '>f4', '>f4', '>f4',
            '>f4', '>f4','>f4', '>f4', '>f4', '>f8', '>f8', 'S20',
            '>S20', '>i8', 'S20')
            )
        obs_tables.append(t_obs)

    hdu_table = vstack(hdu_tables)

    hdu_header = DEFAULT_HEADER.copy()
    hdu_header["HDUCLAS1"] = "INDEX"
    hdu_header["HDUCLAS2"] = "HDU"
    hdu_header["TELESCOP"] = "CTA"
    hdu_header["INSTRUME"] = "LST-1"

    filename_hdu_table = fits_dir/'hdu-index.fits.gz'

    hdu = fits.BinTableHDU(hdu_table, header=hdu_header, name='HDU INDEX')
    hdu_list = fits.HDUList([fits.PrimaryHDU(), hdu])
    hdu_list.writeto(filename_hdu_table, overwrite=True)

    obs_table = vstack(obs_tables)

    obs_header = hdu_header.copy()
    obs_header["HDUCLAS2"] = "OBS"
    obs_header['MJDREFI'] = event_table.meta['MJDREFI']
    obs_header['MJDREFF'] = event_table.meta['MJDREFF']

    filename_obs_table = fits_dir/'obs-index.fits.gz'

    obs = fits.BinTableHDU(obs_table, header = obs_header, name='OBS INDEX')
    hdu_list = fits.HDUList([fits.PrimaryHDU(), obs])
    hdu_list.writeto(filename_obs_table, overwrite=True)

    return

def create_event_list(data, run_number, source_name, mode):
    """
    Create the event_list BinTableHDUs from the given data

    Parameters
    ----------
        Data: DL2 data file
                'astropy.table.QTable'
        Run: Run number
                Int
        Source_name: Name of the source
                Str
        Mode: Observation mode
                Str, eg: ON, OFF, WOBBLE
    Returns
    -------
        Events HDU:  `astropy.io.fits.BinTableHDU`
        GTI HDU:  `astropy.io.fits.BinTableHDU`
        Pointing HDU:  `astropy.io.fits.BinTableHDU`
    """
    name=source_name

    # Timing parameters
    lam = 2800 #Average rate of triggered events, taken by hand for now
    t_start = data['dragon_time'][0].value
    t_stop = data['dragon_time'][-1].value
    time = Time(data['dragon_time'], format='unix', scale="utc")
    date_obs = time[0].to_value('iso', 'date')
    obs_time = t_stop-t_start #All corrections excluded

    pointing_alt = data['pointing_alt']
    pointing_az = data['pointing_az']

    horizon_frame = AltAz(location=location, obstime=time)
    coord_pointing = SkyCoord(alt=pointing_alt, az=pointing_az, frame=horizon_frame)
    coord = SkyCoord(alt=data['reco_alt'], az=data['reco_az'], frame=horizon_frame)

    object_radec = SkyCoord.from_name(source_name)

    ##########################################################################
    ### Event table
    event_table = QTable(
            {
                "EVENT_ID": u.Quantity(data['event_id']),
                "TIME": u.Quantity(data['dragon_time']),
                "RA": u.Quantity(coord.icrs.ra.to(u.deg)),
                "DEC": u.Quantity(coord.icrs.dec.to(u.deg)),
                "ENERGY": u.Quantity(data['reco_energy'])
            }
        )
    ##########################################################################
    ### GTI table
    gti_table = QTable(
        {
            "START" : u.Quantity(t_start, ndmin=1),
            "STOP" : u.Quantity(t_stop, ndmin=1)
        }
    )
    ##########################################################################
    ### Adding the meta data
    ### Event table metadata
    ev_header = DEFAULT_HEADER.copy()
    ev_header["HDUCLAS1"] = "EVENTS"

    ev_header["OBS_ID"] = run_number
    ev_header["DATE_OBS"] = date_obs
    ev_header["TSTART"] = t_start
    ev_header["TSTOP"] = t_stop
    ev_header["MJDREFI"] = '40587' #Time('', format='mjd', scale="utc") # Unix 01/01/1970 0h0m0
    ev_header["MJDREFF"] = '0' #Time('0',format='mjd',scale='utc')
    ev_header["TIMEUNIT"] = 's'
    ev_header["TIMESYS"] = "UTC"
    ev_header["OBJECT"] = name
    ev_header["OBS_MODE"] = mode
    ev_header["N_TELS"] = data["tel_id"][0]
    ev_header["TELLIST"] = f'LST-{data["tel_id"][0]}'

    ev_header["RA_PNT"] = coord_pointing.icrs.ra.value
    ev_header["DEC_PNT"] = coord_pointing.icrs.dec.value
    ev_header["ALT_PNT"] = round(np.rad2deg(data['pointing_alt'].value.mean()),6)
    ev_header["AZ_PNT"] = round(np.rad2deg(data['pointing_az'].value[0]),6)
    ev_header["RA_OBJ"] = object_radec.ra.value
    ev_header["DEC_OBJ"] = object_radec.dec.value
    ev_header["FOVALIGN"] = 'ALTAZ'

    ev_header["ONTIME"] = obs_time
    #Dead time for DRS4 chip is 26 u_sec
    ev_header["DEADC"] = 1/(1+2.6e-5*lam) # 1/(1 + dead_time*lambda)
    ev_header["LIVETIME"] = ev_header["DEADC"]*ev_header["ONTIME"]

    ##########################################################################
    ### GTI table metadata
    gti_header = DEFAULT_HEADER.copy()
    gti_header["HDUCLAS1"] = "GTI"

    gti_header["OBS_ID"]=run_number
    gti_header["MJDREFI"] = ev_header["MJDREFI"]
    gti_header["MJDREFF"] = ev_header["MJDREFF"]
    gti_header["TIMESYS"] = ev_header["TIMESYS"]
    gti_header["TIMEUNIT"] = ev_header["TIMEUNIT"]

    ##########################################################################
    ### Pointing table metadata
    pnt_header = DEFAULT_HEADER.copy()
    pnt_header["HDUCLAS1"] = "POINTING"

    pnt_header["OBS_ID"] = run_number
    pnt_header["RA_PNT"] = coord_pointing.icrs.ra.value
    pnt_header["DEC_PNT"] = coord_pointing.icrs.dec.value
    pnt_header["ALT_PNT"] = ev_header["ALT_PNT"]
    pnt_header["AZ_PNT"] = ev_header["AZ_PNT"]
    pnt_header["TIME"] = t_start

    ### Create HDUs
    #########################################################################
    pnt_table = QTable()

    event = fits.BinTableHDU(event_table, header = ev_header, name = 'EVENTS')
    gti = fits.BinTableHDU(gti_table, header = gti_header, name = 'GTI')
    pointing = fits.BinTableHDU(pnt_table, header = pnt_header, name = 'POINTING')

    return event, gti, pointing
