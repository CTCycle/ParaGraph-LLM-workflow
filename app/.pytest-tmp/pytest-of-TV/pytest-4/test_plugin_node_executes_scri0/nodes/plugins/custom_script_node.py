def execute(parameters, inputs):
    prefix = str(parameters.get('prefix', ''))
    text = str(inputs.get('text', ''))
    return {'result': f"{prefix}{text}".upper()}