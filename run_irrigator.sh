echo 'run_irrigator.sh' > /home/pi/logs/run_irrigator_out.txt 2> /home/pi/logs/run_irrigator_err.txt
source /home/pi/miniconda3/bin/activate irrigator >> /home/pi/logs/run_irrigator_out.txt 2>> /home/pi/logs/run_irrigator_err.txt
cd /home/pi/git/irrigator
# export the environment variables from secrets.sh
# (copy from secrets.sh.default and fill in your values)
source ./secrets.sh >> /home/pi/logs/run_server_out.txt 2>> /home/pi/logs/run_server_err.txt

./irrigator.py >> /home/pi/logs/run_irrigator_out.txt 2>> /home/pi/logs/run_irrigator_err.txt
echo 'finished' >> /home/pi/logs/run_irrigator_out.txt 2>> /home/pi/logs/run_irrigator_err.txt
