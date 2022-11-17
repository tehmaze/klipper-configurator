#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys

from jsonschema import validate
import yaml

BASE_PATH = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..',
))
SCHEMA_PATH = os.path.join(BASE_PATH, 'schema')
BOARD_SCHEMA_NAME = os.path.join(SCHEMA_PATH, 'board.yaml')
MCU_SCHEMA_NAME = os.path.join(SCHEMA_PATH, 'mcu.yaml')


VALID_PIN_NAMES = dict(
    avr=re.compile(r'^P[A-L][0-7]$'),
    atsam=re.compile(r'^P[A-E](?:[0-9]|[12][0-9]|3[0-1])$'),
    atsamd=re.compile(r'^P[A-D](?:[0-9]|[12][0-9]|3[0-1])$'),
    lpc176x=re.compile(r'^P[0-4]\.(?:[0-9]|[12][0-9]|3[0-1])$'),
    pru=re.compile(r'^gpio[0-3]_(?:[0-9]|[12][0-9]|3[0-1])$'),
    rp2040=re.compile(r'^gpio(?:[0-9]|[12][0-9]|30)$'),
    stm32=re.compile(r'^P[A-I](?:[0-9]|1[0-5])$')
)


def _load_yaml(name):
    #print('loading', name)
    with open(name, 'r') as stream:
        return yaml.safe_load(stream)


def load_board_definition(name, board_schema):
    #print('convert', name)
    #print(repr(schema))
    data = _load_yaml(name)
    validate(data, board_schema)
    return data


class MCUValidator:
    pins = {
        'motor': {
            'type': 'list_of_blocks',
            'required': {'enable', 'step', 'dir'},
            'optional': {'diag_pin',},
            'shared': {'uart_pin', 'rx_pin'},
            'skip': {'alias',},
        },
        'limit': {
            'type': 'dict',
        },
        'fan': {
            'type': 'dict',
        },
        'heater': {
            'type': 'dict',
        },
        'heater_bed': {
            'type': 'dict',
            'extra': True,
        },
        'sensor': {
            'type': 'dict',
        },
        'sensor_bed': {
            'type': 'dict',
            'extra': True,
        },
        'alias': {
            'type': 'dict',
            'extra': True,
        }
    }

    def __init__(self, mcu_class):
        self.pin_valid = VALID_PIN_NAMES[mcu_class]
        
    def verify(self, board):
        # reset state
        self.used_pins = {}
        self.used_names = set()

        for group, pins in self.pins.items():
            if group not in board:
                if self.pins[group].get('extra', False):
                    continue

                raise ValueError("group '{}' is missing in definition".format(group))
            
            if pins['type'] == 'list_of_blocks':
                self._verify_blocks_pins(pins, group, board[group])
            elif pins['type'] == 'dict':
                self._verify_dict_pins(group, board[group])
    
    def _verify_blocks_pins(self, pins, group, blocks):
        required = pins.get('required', set())
        optional = pins.get('optional', set())
        shared = pins.get('shared', set())
        skip = pins.get('skip', set())

        for i, block in enumerate(blocks):
            if set(block.keys()) & skip:
                continue

            name = block['name']
            if name in self.used_names:
                ValueError("duplicate name '{}' for block {} in group {}".format(name, i, group))
            self.used_names |= {name,}

            try:
                self._verify_pins(block, required, shared, optional)
            except ValueError as e:
                #name = '{}'.format(i)
                #if 'name' in block:
                #    name = "{} ('{}')".format(i, block['name'])
                raise ValueError("error in block {} of group '{}': {}".format(
                    name, group, e))

    def _verify_dict_pins(self, group, items):
        #print('items', repr(items))
        for name, pin in items.items():
            if name in self.used_names:
                raise ValueError("name '{}' already exists".format(name))
            
            if pin in self.used_pins:
                raise ValueError("pin '{}' is already in use by {}".format(pin, self.used_pins[pin]))

            self.verify_pin_name(pin)
            self.used_pins[pin] = '{}[{}]'.format(group, name)

    def _verify_pins(self, pins, required, shared, optional):
        all_pins = required | shared | optional
        for pin in all_pins:
            if pin not in pins:
                if pin in required:
                    raise ValueError("pin '{}' is not defined".format(pin))
                continue

            if pins[pin] in self.used_pins:
                if pin not in shared:
                    raise ValueError("pin '{}' is already in use by {}".format(pins[pin], self.used_pins[pins[pin]]))

            self.verify_pin_name(pins[pin])
            self.used_pins[pins[pin]] = '?'

    def verify_pin_name(self, name):
        if not self.pin_valid.match(name):
            raise ValueError("invalid pin name '{}'".format(name))
        return True


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--board-schema', default=BOARD_SCHEMA_NAME)
    parser.add_argument('-m', '--mcu-schema', default=MCU_SCHEMA_NAME)
    parser.add_argument('-o', '--output', default='boards.json')
    parser.add_argument('definition', nargs='+')
    
    args = parser.parse_args()

    board_schema = _load_yaml(args.board_schema)
    #print('board', repr(board_schema))
    mcu_schema = _load_yaml(args.mcu_schema)
    #print('mcu', mcu_schema)

    boards = {}
    mcus = {}
    for name in args.definition:
        model = os.path.basename(name)
        model = model.rsplit('.', 2)[0]

        print('processing model', model)
        boards[model] = load_board_definition(name, board_schema)

        mcu_class = boards[model]['mcu']['class']
        if mcu_class not in mcus:
            mcus[mcu_class] = MCUValidator(mcu_class)
        
        try:
            mcus[mcu_class].verify(boards[model])
        except ValueError as e:
            print('board definition', name, 'contains errors:', e)
            return 1

    #print(boards)
    with open(args.output, 'w') as stream:
        json.dump(boards, stream, indent=2)


if __name__ == '__main__':
    sys.exit(run())