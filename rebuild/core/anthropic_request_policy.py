"""Explicit prospective execution parameters; absent means historical defaults.

No clinical schema, prompt, payload, model, rates or token/time limits are
changed here. The same finite policy is used by all Anthropic request paths.
"""
from copy import deepcopy

CONFIG_KEY = 'anthropic_request_profile'
PROFILE = 'sonnet55-between-tools-high-v1'
ENVELOPE_KEY = 'anthropic_request_parameters'
MODEL = 'claude-sonnet-5-5'
PARAMETERS = {'thinking': {'type': 'between_tools'}, 'output_config': {'effort': 'high'}}


class PolicyError(ValueError):
    pass


def parameters(config):
    """Reconstruct only the explicitly recorded profile, never upgrade history."""
    if type(config) is not dict:
        raise PolicyError('Anthropic request configuration must be an object.')
    if CONFIG_KEY not in config:
        return {}
    if (type(config[CONFIG_KEY]) is not str or config[CONFIG_KEY] != PROFILE
            or config.get('mode') != 'live' or config.get('provider') != 'anthropic'
            or type(config.get('model')) is not str or config['model'] != MODEL):
        raise PolicyError('Unsupported explicit Anthropic request profile.')
    return deepcopy(PARAMETERS)


def prospective(config):
    """Select the reviewed profile for a new compatible request configuration."""
    parameters(config)  # Explicit invalid values never become a new default.
    if (config.get('mode') == 'live' and config.get('provider') == 'anthropic'
            and type(config.get('model')) is str and config['model'] == MODEL):
        return {**config, CONFIG_KEY: PROFILE}
    return dict(config)


def apply(envelope, config):
    """Preserve the full envelope/schema and add only the recorded parameters."""
    result = deepcopy(envelope)
    selected = parameters(config)
    if selected:
        result['thinking'] = selected['thinking']
        result['output_config'] = {**result.get('output_config', {}), **selected['output_config']}
    return result
