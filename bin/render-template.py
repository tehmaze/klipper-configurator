#!/usr/bin/env python3

import argparse
from collections import OrderedDict
import jinja2
import json
import sys

from jinja2 import nodes
from jinja2.ext import Extension


class Motor(dict):
    @property
    def is_extruder(self):
        return self.get('name').upper().startswith('e')


class Motors:
    def __init__(self, motors):
        self.motors = OrderedDict()
        for motor in motors:
            self.motors[motor['name']] = Motor(motor)
        
        self._used = set()
    
    @property
    def X(self):
        '''Return first qualifying X motor'''
        return self.motor('X') or self.motor()

    @property
    def Y(self):
        '''Return first qualifying Y motor'''
        return self.motor('Y') or self.motor()

    @property
    def Z(self):
        '''Return first qualifying Z motor'''
        return self.motor('Z') or self.motor()

    @property
    def E(self):
        '''Return first qualifying Z motor'''
        return self.motor('E') or self.motor()

    def motor(self, prefix=''):
        '''Return a motor slot'''
        prefix = prefix.upper()
        for name, motor in self.motors.items():
            if name not in self._used and name.upper().startswith(prefix):
                self._used.add(name)
                return motor


class Heaters:
    def __init__(self, heaters, bed_heaters):
        self.heaters = []
        self.bed_heaters = []

        for k, v in sorted(heaters.items()):
            self.heaters.append(dict(name=k, pin=v))
        for k, v in sorted(bed_heaters.items()):
            self.bed_heaters.append(dict(name=k, pin=v))

    @property
    def heater(self):
        return self.heaters.pop(0)

    @property
    def heater_bed(self):
        if len(self.bed_heaters) == 0:
            return self.heater
        return self.bed_heaters.pop(0)
    

class Sensors:
    def __init__(self, sensors, bed_sensors):
        self.sensors = []
        self.bed_sensors = []

        for k, v in sorted(sensors.items()):
            self.sensors.append(dict(name=k, pin=v))
        for k, v in sorted(bed_sensors.items()):
            self.bed_sensors.append(dict(name=k, pin=v))

    @property
    def sensor(self):
        return self.sensors.pop(0)

    @property
    def sensor_bed(self):
        if len(self.bed_sensors) == 0:
            return self.sensor
        return self.bed_sensors.pop(0)

def load_board(name):
    with open('boards.json', 'r') as stream:
        data = json.load(stream)[name]

        # Wrap some helpers
        data['motor'] = Motors(data['motor'])
        data['heater'] = Heaters(data['heater'], data.get('heater_bed', {}))
        data['sensor'] = Sensors(data['sensor'], data.get('sensor_bed', {}))

        return data


def render_template(name, board, printer, output=sys.stdout):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader([
            '.',
            '../template',
            'template',
        ]),
    )
    t = env.get_template(name)
    output.write(t.render(board=board, printer=printer))

    #with open(name, 'r') as stream:
    #    jinja2.


def parse_size(spec):
    spec = [int(x) for x in spec.split('x')]
    while len(spec) < 3:
        spec.append(250)
    return dict(x=spec[0], y=spec[1], z=spec[2])


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--board')
    parser.add_argument('-s', '--size', default='250x250x250')
    parser.add_argument('template')

    args = parser.parse_args()
    board = load_board(args.board)
    printer = dict(size=parse_size(args.size))
    #print(repr(printer))
    render_template(args.template, board, printer)


if __name__ == '__main__':
    sys.exit(run())