from io import BytesIO
import tarfile
import gzip
import base64
import os.path
import shutil

def unpack_user_folders(target_folder, buf_str):
  im_memory_tar = tarfile.open(fileobj = gzip.GzipFile(fileobj = BytesIO(base64.b64decode(buf_str))), mode = 'r')
  im_memory_tar.extractall(target_folder)

def pack_user_folders(user_data_folder):
  new_buffer = BytesIO()
  with tarfile.open(fileobj = new_buffer, mode = 'w|gz') as new_tar:
    for check_folder in [ 'Default/Cookies', 'Default/Cookies-journal', 'Default/Local Storage',
      'Default/SharedStorage', 'Default/SharedStorage-wal', 'Default/WebStorage' ] :
      source_dir = os.path.join(user_data_folder, check_folder)
      if os.path.exists(source_dir) :
        new_tar.add(name = source_dir, arcname = check_folder)
  return base64.b64encode(new_buffer.getvalue()).decode('ascii')

def remove_user_folders(user_data_folder):
  for check_folder in [ 'Default/Cookies', 'Default/Cookies-journal', 'Default/Local Storage',
    'Default/SharedStorage', 'Default/SharedStorage-wal', 'Default/WebStorage' ] :
    remove_dir = os.path.join(user_data_folder, check_folder)
    shutil.rmtree(remove_dir, ignore_errors = True)

#unpack_user_folders('./test_result/', pack_user_folders('./test_source/'))
