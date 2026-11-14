"""Fail closed when a loaded SDK cannot expose explicit timeout/retry fields."""
def bounded_model(model,timeout=30,output_tokens=2048):
    if type(timeout) not in (int,float) or not 0<timeout<=60 or type(output_tokens) is not int or not 1<=output_tokens<=2048:
        raise ValueError('Invalid provider timeout/token bounds')
    fields=getattr(type(model),'model_fields',{})
    key=next((name for name in ('timeout','request_timeout') if name in fields),None)
    if key is None or 'max_retries' not in fields or 'max_output_tokens' not in fields or not callable(getattr(model,'model_copy',None)):
        raise ValueError('Provider timeout interface has not been verified')
    return model.model_copy(update={key:timeout,'max_retries':0,'max_output_tokens':output_tokens})
