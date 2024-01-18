import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app_mods


tcc = app_mods.Tiu_CreateConfig('../../../Finvasia_login/cred/tarak_fv.yml',
                                None, None, False,
                                '../log', None, False, None)
tiu = app_mods.Tiu(tcc=tcc)

tiu.fv_ac_balance()
tiu.update_holdings()
tiu.update_positions()

print(json.dumps(tiu.get_security_info('NFO', 'NIFTY18JAN24C21600'), indent=2))

# symbol_list = ['RELIANCE', 'ACC', 'TCS', 'INFY', 'PNB']
# tiu.create_sym_token_tsym (symbol_list)

# tiu.fetch_data (symbol_list=symbol_list, tf=3, output_directory=r'F:\Market_Data\temp\test')
# symbol_list = ['TCS', 'INFY']
# tiu.create_sym_token_tsym (symbol_list)
# tiu.download_data_parallel (symbol_list=symbol_list, tf=3, output_directory=r'F:\Market_Data\temp\test')

# print (tiu.get_enabled_gtts ())
# print (tiu.get_pending_gtt_order())

# sym_dict = {'Strategy_id': 1, 'TimeNum': "", 'Symbol': 'PNB', 'High': 92, 'Low': 90, 'ST': 91}
# ret = tiu.place_mm_fc_gtt_order (sym_dict, 10000)
# print (ret)
