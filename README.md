# Cite Build Server

## development

### install buildbot
```
pip install -U buildbot  buildbot-worker buildbot-www buildbot-console-view buildbot-waterfall-view 
pip install -U txrequests
```

### if using mysql

```
pip install -U MySQL-python
```

### setup master
1. create master

    ```buildbot create-master master```

2. link master script to master directory

    ```ln -s `pwd`/master_cite.py master/master.cfg```

3. link master config

    ```
    sudo mkdir /var/lib/buildbot
    sudo ln -s `pwd`/build.conf /var/lib/buildbot/build.conf
    ```

4. start master

    ```buildbot start master```

5. see log
    
    ```tail -f master/twistd.log```

### setup worker
1. create worker

    ```buildbot-worker create-worker worker localhost cite-build01-01 cite-buildbot-worker```

2. start worker

    ```buildbot-worker start worker```

3. see log

    ```tail -f worker/twistd.log```

## package
```
docker build -t docker-reg.c.9rum.cc/cite-core/cite-build .
```

## reference
* buildbot docs : http://docs.buildbot.net/latest/
