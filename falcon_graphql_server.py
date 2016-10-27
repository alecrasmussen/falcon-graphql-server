#!/usr/bin/env python3
# coding: utf-8
#
# To run:
# $ gunicorn graphene_server:graphQL_api -b localhost:4004
#
# To use, POST as application/json with query, variables, & operationName args:
# $ curl -H 'Content-Type: application/json' \
#     -d '{"query":"query RollDice($dice: Int!, $sides: Int){rollDice(dice:$dice,sides:$sides)}","variables":"{\"dice\": 8,\"sides\":9}","operationName":"RollDice"}' \
#     "http://localhost:4004/graphql"
#
# You can also use the GraphiQL dashboard:
# $ open "http://localhost:4004/graphiql"

from collections import OrderedDict
from contextlib import redirect_stdout
import json
from os import devnull
from random import randrange

import falcon
import graphene


# Define a GraphQL query schema
class Query(graphene.ObjectType):
    "A Graphene schema. Utilized by GraphQLResource."
    hello = graphene.String(description='A basic GraphQL object.')
    extra = graphene.String(description='Another basic GraphQL object.')
    roll_dice = graphene.List(description='A GraphQL object with arguments.',
                              of_type=graphene.Int,
                              args=dict(
                                  dice=graphene.NonNull(of_type=graphene.Int),
                                  sides=graphene.Int())
                              )

    def resolve_hello(self, args, context, info):
        return 'Hello world!'

    def resolve_extra(self, args, context, info):
        return 'Extra!'

    def resolve_roll_dice(self, args, context, info):
        num_dice = range(args.get('dice'))
        return [randrange(1, args.get('sides', 6) + 1) for i in num_dice]


# Create the schema that will be used to resolve GraphQL requests.
schema = graphene.Schema(query=Query)


def set_graphql_allow_header(req, resp, resource):
    "Sets the 'Allow' header on responses to GraphQL requests."
    resp.set_header('Allow', 'GET, POST, OPTIONS')


# Define the GraphQL API endpoint
@falcon.after(set_graphql_allow_header)
class GraphQLResource:
    "Main GraphQL server. Integrates with the predefined Graphene schema."
    def on_options(self, req, resp):
        "Handles OPTIONS requests."
        resp.status = falcon.HTTP_204
        pass

    def on_head(self, req, resp):
        "Handles HEAD requests. No content."
        pass

    def on_get(self, req, resp):
        """Handles GraphQL GET requests.

        example:
          curl -g "http://localhost:4004/graphql?query={hello}"

        complex example:
          curl -G "http://localhost:4004/graphql" \
            --data-urlencode 'query=query RollDice($dice: Int!, $sides: Int) { rollDice(dice: $dice, sides: $sides)}' \
            --data-urlencode 'variables={"dice": 5, "sides": 9}' \
            --data-urlencode 'operationName=RollDice'
        
        above example in url-encoded form:
          curl "http://localhost:4004/graphql?query=query%20RollDice%28%24dice%3A%20Int%21%2C%20%24sides%3A%20Int%29%20%7B%20rollDice%28dice%3A%20%24dice%2C%20sides%3A%20%24sides%29%7D&variables=%7B%22dice%22%3A%205%2C%20%22sides%22%3A%209%7D&operationName=RollDice"

        """

        if req.params and 'query' in req.params and req.params['query']:
            query = str(req.params['query'])
        else:
            # this means that there aren't any query params in the url
            resp.status = falcon.HTTP_400
            resp.body = json.dumps(
                {"errors": [{"message": "Must provide query string."}]},
                separators=(',', ':')
            )
            return

        if 'variables' in req.params and req.params['variables']:
            try:
                variables = json.loads(str(req.params['variables']),
                                       object_pairs_hook=OrderedDict)
            except json.decoder.JSONDecodeError:
                resp.status = falcon.HTTP_400
                resp.body = json.dumps(
                    {"errors": [{"message": "Variables are invalid JSON."}]},
                    separators=(',', ':')
                )
                return
        else:
            variables = ""

        if 'operationName' in req.params and req.params['operationName']:
            operation_name = str(req.params['operationName'])
        else:
            operation_name = None

        # redirect stdout of schema.execute to /dev/null
        with open(devnull, 'w') as f:
            with redirect_stdout(f):
                # run the query
                if operation_name is None:
                    result = schema.execute(query, variable_values=variables)
                else:
                    result = schema.execute(query, variable_values=variables,
                                            operation_name=operation_name)

        # construct the response and return the result
        if result.data:
            data_ret = {'data': result.data}
            resp.status = falcon.HTTP_200
            resp.body = json.dumps(data_ret, separators=(',', ':'))
            return
        elif result.errors:
            # NOTE: these errors don't include the optional 'locations' key
            err_msgs = [{'message': str(i)} for i in result.errors]
            resp.status = falcon.HTTP_400
            resp.body = json.dumps({'errors': err_msgs}, separators=(',', ':'))
            return
        else:
            # responses should always have either data or errors
            raise

    def on_post(self, req, resp):
        """Handles GraphQL POST requests.

        1. requests with ?query={query_string} parameters in url
        (this takes precedence over POST request bodies, will be used first)
        (can also be used in tandem with POST body)

        examples:
          curl -H "Content-Type: application/json" \
            -d "{}" \
            -g "http://localhost:4004/graphql?query={hello}"

          curl -g -H "Content-Type: application/graphql" \
            -d 'query RollDice($dice: Int!, $sides: Int){rollDice(dice:$dice,sides:$sides)}' \
            'http://localhost:4004/graphql?variables={"dice":5}'

        2. 'content-type: application/json' requests
        (this is the preferred method, used by graphiql)

        examples:
          curl -H 'Content-Type: application/json' \
            -d '{"query": "{hello}"}' \
            "http://localhost:4004/graphql"

          curl -H 'Content-Type: application/json' \
            -d '{"query":"query RollDice($dice: Int!, $sides: Int){rollDice(dice:$dice,sides:$sides)}","variables":"{\"dice\": 8,\"sides\":9}","operationName":"RollDice"}' \
            "http://localhost:4004/graphql"

        3. 'content-type: application/graphql' requests
        (request body is the query string; pass variables/operationName in url)

        example:
          curl -H 'Content-Type: application/graphql' \
            -d '{hello}' \
            "http://localhost:4004/graphql"

        4. 'content-type: application/x-www-form-urlencoded' requests

        examples:
          curl -d 'query={hello}' "http://localhost:4004/graphql"

          curl "http://localhost:4004/graphql" \
            --data-urlencode 'query=query RollDice($dice: Int!, $sides: Int) { rollDice(dice: $dice, sides: $sides)}' \
            --data-urlencode 'variables={"dice": 5, "sides": 9}' \
            --data-urlencode 'operationName=RollDice'

        """

        # parse url parameters in the request first
        if req.params and 'query' in req.params and req.params['query']:
            query = str(req.params['query'])
        else:
            query = None

        if 'variables' in req.params and req.params['variables']:
            try:
                variables = json.loads(str(req.params['variables']),
                                       object_pairs_hook=OrderedDict)
            except json.decoder.JSONDecodeError:
                resp.status = falcon.HTTP_400
                resp.body = json.dumps(
                    {"errors": [{"message": "Variables are invalid JSON."}]},
                    separators=(',', ':')
                )
                return
        else:
            variables = None

        if 'operationName' in req.params and req.params['operationName']:
            operation_name = str(req.params['operationName'])
        else:
            operation_name = None

        # Next, handle 'content-type: application/json' requests
        if req.content_type and 'application/json' in req.content_type:
            # error for requests with no content
            if req.content_length in (None, 0):
                resp.status = falcon.HTTP_400
                resp.body = json.dumps(
                    {"errors": [{"message": "POST body sent invalid JSON."}]},
                    separators=(',', ':')
                )
                return

            # read and decode request body
            raw_json = req.stream.read()
            try:
                req.context['post_data'] = json.loads(
                                               raw_json.decode('utf-8'),
                                               object_pairs_hook=OrderedDict
                                           )
            except json.decoder.JSONDecodeError:
                resp.status = falcon.HTTP_400
                resp.body = json.dumps(
                    {"errors": [{"message": "POST body sent invalid JSON."}]},
                    separators=(',', ':')
                )
                return

            # build the query string (Graph Query Language string)
            if (query is None and req.context['post_data'] and
                    'query' in req.context['post_data']):
                query = str(req.context['post_data']['query'])
            elif query is None:
                resp.status = falcon.HTTP_400
                resp.body = json.dumps(
                    {"errors": [{"message": "Must provide query string."}]},
                    separators=(',', ':')
                )
                return

            # build the variables string (JSON string of key/value pairs)
            if (variables is None and req.context['post_data'] and
                    'variables' in req.context['post_data'] and
                    req.context['post_data']['variables']):
                variables = str(req.context['post_data']['variables'])
                try:
                    json_str = str(req.context['post_data']['variables'])
                    variables = json.loads(json_str,
                                           object_pairs_hook=OrderedDict)
                except json.decoder.JSONDecodeError:
                    resp.status = falcon.HTTP_400
                    resp.body = json.dumps(
                        {"errors": [
                            {"message": "Variables are invalid JSON."}
                        ]},
                        separators=(',', ':')
                    )
                    return
            elif variables is None:
                variables = ""

            # build the operationName string (matches a query or mutation name)
            if (operation_name is None and
                    'operationName' in req.context['post_data'] and
                    req.context['post_data']['operationName']):
                operation_name = str(req.context['post_data']['operationName'])

        # Alternately, handle 'content-type: application/graphql' requests
        elif req.content_type and 'application/graphql' in req.content_type:
            # read and decode request body
            req.context['post_data'] = req.stream.read().decode('utf-8')

            # build the query string
            if query is None and req.context['post_data']:
                query = str(req.context['post_data'])

            elif query is None:
                resp.status = falcon.HTTP_400
                resp.body = json.dumps(
                    {"errors": [{"message": "Must provide query string."}]},
                    separators=(',', ':')
                )
                return

        # Skip application/x-www-form-urlencoded since they are automatically
        # included by setting req_options.auto_parse_form_urlencoded = True

        elif query is None:
            # this means that the content-type is wrong and there aren't any
            # query params in the url
            resp.status = falcon.HTTP_400
            resp.body = json.dumps(
                {"errors": [{"message": "Must provide query string."}]},
                separators=(',', ':')
            )
            return

        # redirect stdout of schema.execute to /dev/null
        with open(devnull, 'w') as f:
            with redirect_stdout(f):
                # run the query
                if operation_name is None:
                    result = schema.execute(query, variable_values=variables)
                else:
                    result = schema.execute(query, variable_values=variables,
                                            operation_name=operation_name)

        # construct the response and return the result
        if result.data:
            data_ret = {'data': result.data}
            resp.status = falcon.HTTP_200
            resp.body = json.dumps(data_ret, separators=(',', ':'))
            return
        elif result.errors:
            # NOTE: these errors don't include the optional 'locations' key
            err_msgs = [{'message': str(i)} for i in result.errors]
            resp.status = falcon.HTTP_400
            resp.body = json.dumps({'errors': err_msgs}, separators=(',', ':'))
            return
        else:
            # responses should always have either data or errors
            raise

    def on_put(self, req, resp):
        resp.status = falcon.HTTP_405
        resp.body = json.dumps(
            {"errors": [
                {"message": "GraphQL only supports GET and POST requests."}
            ]},
            separators=(',', ':')
        )

    def on_patch(self, req, resp):
        resp.status = falcon.HTTP_405
        resp.body = json.dumps(
            {"errors": [
                {"message": "GraphQL only supports GET and POST requests."}
            ]},
            separators=(',', ':')
        )

    def on_delete(self, req, resp):
        resp.status = falcon.HTTP_405
        resp.body = json.dumps(
            {"errors": [
                {"message": "GraphQL only supports GET and POST requests."}
            ]},
            separators=(',', ':')
        )


class StaticGraphiQLResource:
    "Serves GraphiQL dashboard. Meant to be used during development only."
    def on_get(self, req, resp, static_file=None):
        "Handles GraphiQL get requests."
        if static_file is None:
            static_file = 'graphiql.html'
            resp.content_type = 'text/html; charset=UTF-8'
        elif static_file == 'graphiql.css':
            resp.content_type = 'text/css; charset=UTF-8'
        else:
            resp.content_type = 'application/javascript; charset=UTF-8'

        resp.status = falcon.HTTP_200
        resp.stream = open('graphiql/' + static_file, 'rb')


# Load the API object
graphQL_api = falcon.API()

# Keep query parameters even when they have no corresponding values (aka flags)
graphQL_api.req_options.keep_blank_qs_values = True

# Automatically parse a www-form-urlencoded POST body & insert into req.params
graphQL_api.req_options.auto_parse_form_urlencoded = True

# Connect routes to resources
graphQL_route = GraphQLResource()

# Attach main routes to API
graphQL_api.add_route('/graphql', graphQL_route)
graphQL_api.add_route('/graphiql', StaticGraphiQLResource())
graphQL_api.add_route('/graphiql/{static_file}', StaticGraphiQLResource())
