"""
Monitors and controls the Tesla gateway.
"""
import logging

import asyncio
import voluptuous as vol
import teslapy
from datetime import time, datetime

from homeassistant.const import (
    CONF_USERNAME
    )
import homeassistant.helpers.config_validation as cv
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)

@asyncio.coroutine
def async_setup(hass, config):

    domain_config = config[DOMAIN]
    conf_user = domain_config[CONF_USERNAME]
    
    tesla = teslapy.Tesla(domain_config[CONF_USERNAME])

    def get_battery():
        batteries = tesla.battery_list()
        if len(batteries) > 0:
            return batteries[0]
        else:
            return None

    @asyncio.coroutine
    async def set_operation(service):
        
        battery = await hass.async_add_executor_job(get_battery)
        if not battery:
            _LOGGER.warning('Battery object is None')
            return None

        await hass.async_add_executor_job(battery.set_operation, service.data['real_mode'])
        if 'backup_reserve_percent' in service.data:
            await hass.async_add_executor_job(battery.set_backup_reserve_percent, service.data['backup_reserve_percent'])
        elif 'offset' in service.data:
            battery_data = await hass.async_add_executor_job(battery.get_battery_data)
            if 'percentage_charged' in battery_data:
                charge  = (float(battery_data['energy_left']) / float(battery_data['total_pack_energy'])) * 100
                charge  = int(round(charge))
                reserve = service.data['offset'] + charge
                reserve = max(0, min(100, reserve))
                await hass.async_add_executor_job(battery.set_backup_reserve_percent, reserve)

    hass.services.async_register(DOMAIN, 'set_operation', set_operation)

    @asyncio.coroutine
    async def set_reserve(service):
        
        battery = await hass.async_add_executor_job(get_battery)
        if not battery:
            _LOGGER.warning('Battery object is None')
            return None
            
        if 'backup_reserve_percent' in service.data:
            await hass.async_add_executor_job(battery.set_backup_reserve_percent, service.data['backup_reserve_percent'])
        elif 'offset' in service.data:
            battery_data = await hass.async_add_executor_job(battery.get_battery_data)
            if 'percentage_charged' in battery_data:
                charge  = (float(battery_data['energy_left']) / float(battery_data['total_pack_energy'])) * 100
                charge  = int(round(charge))
                reserve = service.data['offset'] + charge
                reserve = max(0, min(100, reserve))
                await hass.async_add_executor_job(battery.set_backup_reserve_percent, reserve)

    hass.services.async_register(DOMAIN, 'set_reserve', set_reserve)

    @asyncio.coroutine
    async def set_tariff_wrap(service):   
        battery = await hass.async_add_executor_job(get_battery)
        if not battery:
            _LOGGER.warning('Battery object is None')
            return None
    
        await set_tariff(hass, battery, service)
        
    hass.services.async_register(DOMAIN, 'set_tariff', set_tariff_wrap)

    @asyncio.coroutine
    async def set_import_export(service):
        
        battery = await hass.async_add_executor_job(get_battery)
        if not battery:
            _LOGGER.warning('Battery object is None')
            return None

        await hass.async_add_executor_job(battery.set_import_export,
                                          service.data.get('allow_grid_charging',  None),
                                          service.data.get('allow_battery_export', None))

    hass.services.async_register(DOMAIN, 'set_import_export', set_import_export)

    return True


async def set_tariff(hass, battery, service):
    rawTariff     = service.data['tariff_periods']
    
    def parseRateStr(rateStr):
        rateParts = rateStr.split(" ")
        return (float(rateParts[0]), float(rateParts[1]), rateParts[2])
    
    secondsToTime = lambda s: time(hour=s//3600, minute=(s%3600)//60, second=(s%3600)%60)
    periods       = []
    for curRateStr in rawTariff:
        curRate    = parseRateStr(curRateStr)
        periodCost = teslapy.BatteryTariffPeriodCost(curRate[0], curRate[1], curRate[2])
        for period in rawTariff[curRateStr]:
            period = teslapy.BatteryTariffPeriod(periodCost, secondsToTime(period[0]), secondsToTime(period[1]))
            periods.append(period)

    defCost    = parseRateStr(service.data['default_prices'])
    defCost    = teslapy.BatteryTariffPeriodCost(defCost[0], defCost[1], defCost[2])
    planName   = "Autogen @ {0:%H:%M}".format(datetime.now())
    tariffDict = teslapy.Battery.create_tariff(defCost, periods, service.data['provider'], planName)
    await hass.async_add_executor_job(battery.set_tariff, tariffDict)
        