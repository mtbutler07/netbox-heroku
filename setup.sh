wget https://github.com/netbox-community/netbox/archive/v2.6.2.tar.gz
rm -r ./netbox
mkdir -p ./netbox ./temp
tar -xzf v2.6.2.tar.gz -C temp --strip-components=1
rm v2.6.2.tar.gz
cp -R ./temp/netbox/* ./netbox/
cp ./temp/requirements.txt .
echo napalm >> requirements.txt
echo gunicorn >> requirements.txt
echo whitenoise >> requirements.txt
echo python-dotenv >> requirements.txt
echo dj_database_url >> requirements.txt
rm -r ./temp
rm ./netbox/netbox/configuration.example.py
cp configuration.py ./netbox/netbox/configuration.py
cp settings.py ./netbox/netbox/
python3 netbox/manage.py collectstatic --no-input