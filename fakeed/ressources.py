__author__ = 'maxime'

default_config = '''[DEFAULT]
# limit the upload bandwidth in kByte / s at any time; set value to -1 to disable.
global_max_upload = 200
# simulate a constant upload at this speed (kbyte/s).
constant_upload = 110
# the minimum ratio at any time. (except if limited by GLOBAL_MAX_UPLOAD)
min_ratio = 0.75
# should we use MIN_RATIO and CONSTANT_UPLOAD only if there is leechers ?
secure = yes
# multiply real uploaded bytes by this factor. (except if limited by GLOBAL_MAX_UPLOAD)
upload_factor = 3.5
'''