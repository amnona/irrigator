echo 'run_server.sh' > /home/pi/logs/run_server_out.txt 2> /home/pi/logs/run_server_err.txt
source /home/pi/miniconda3/bin/activate irrigator >> /home/pi/logs/run_irrigator_server.txt 2>> /home/pi/logs/run_server_err.txt
cd /home/pi/git/irrigator
export IRRIGATOR_PASSWORD="hashkaYa"
export FLASK_APP=iserver/iserver.py
flask run >> /home/pi/logs/run_server_out.txt 2>> /home/pi/logs/run_server_err.txt
echo 'finished' >> /home/pi/logs/run_server_out.txt 2>> /home/pi/logs/run_server_err.txt

