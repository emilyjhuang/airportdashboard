# Airplane Patient Dashboard

Code for creating front end and back end for airplane patient dashboard that will include daily updates of patient information and status updates.
Langone GK 

**NOTE** this website will only work if connected to NYU network/IP address


**4. Create a Virtual Environment:**

- _Mac:_

  ```
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- _Windows:_
  ```
  python -m venv .venv
  .venv\Scripts\activate
  ```

**5. Install Dependencies:**

```
pip install -r requirements.txt
```

- _Mac:_
```
export FLASK_APP=webapp/app.py 
python -m flask run
flask run
```

- _Windows:_
```
$env:FLASK_APP="webapp/app.py"
flask run
```


fresh environment

```
rm -rf .venv
python -m venv .venv
source .venv/bin/activate  # On Mac/Linux
pip install -r requirements.txt

```
