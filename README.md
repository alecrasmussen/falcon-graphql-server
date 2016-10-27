# Python GraphQL server example, built with Falcon and Graphene

To install dependencies:
```
python3 -m venv PYTHON3_ENV
source PYTHON3_ENV/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt
```

To run:
```
gunicorn falcon_graphql_server:graphQL_api -b localhost:4004
```

To use, `POST` as `application/json` with `query`, `variables`, & `operationName` args:
```
curl -H 'Content-Type: application/json' \
  -d '{"query":"query RollDice($dice: Int!, $sides: Int){rollDice(dice:$dice,sides:$sides)}","variables":"{\"dice\": 8,\"sides\":9}","operationName":"RollDice"}' \
  "http://localhost:4004/graphql"
```

You can also use the GraphiQL dashboard:
```
open "http://localhost:4004/graphiql"
```

To exit the virtual env, run `deactivate`.
