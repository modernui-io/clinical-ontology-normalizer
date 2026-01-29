"""
Knowledge Graph GraphQL API Layer.

Provides a GraphQL interface for querying the knowledge graph,
including concepts, relationships, reasoning paths, and patient data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
import json
import re
import threading


# =============================================================================
# Enums
# =============================================================================


class GraphQLTypeKind(str, Enum):
    """GraphQL type kinds."""
    SCALAR = "SCALAR"
    OBJECT = "OBJECT"
    INTERFACE = "INTERFACE"
    UNION = "UNION"
    ENUM = "ENUM"
    INPUT_OBJECT = "INPUT_OBJECT"
    LIST = "LIST"
    NON_NULL = "NON_NULL"


class SemanticGroupEnum(str, Enum):
    """UMLS semantic groups."""
    ANAT = "Anatomy"
    CHEM = "Chemicals & Drugs"
    DEVI = "Devices"
    DISO = "Disorders"
    GENE = "Genes & Molecular Sequences"
    GEOG = "Geographic Areas"
    LIVB = "Living Beings"
    OBJC = "Objects"
    OCCU = "Occupations"
    ORGA = "Organizations"
    PHEN = "Phenomena"
    PHYS = "Physiology"
    PROC = "Procedures"
    CONC = "Concepts & Ideas"
    ACTI = "Activities & Behaviors"


class RelationshipTypeEnum(str, Enum):
    """Knowledge graph relationship types."""
    IS_A = "IS_A"
    PART_OF = "PART_OF"
    HAS_FINDING = "HAS_FINDING"
    HAS_CAUSE = "HAS_CAUSE"
    HAS_MANIFESTATION = "HAS_MANIFESTATION"
    CAUSES = "CAUSES"
    MAY_CAUSE = "MAY_CAUSE"
    TREATS = "TREATS"
    MAY_TREAT = "MAY_TREAT"
    PREVENTS = "PREVENTS"
    CONTRAINDICATES = "CONTRAINDICATES"
    INTERACTS_WITH = "INTERACTS_WITH"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    DIAGNOSES = "DIAGNOSES"
    INDICATES = "INDICATES"


# =============================================================================
# GraphQL Type System
# =============================================================================


@dataclass
class GraphQLField:
    """Definition of a GraphQL field."""
    name: str
    type_name: str
    description: str | None = None
    args: dict[str, "GraphQLArgument"] = field(default_factory=dict)
    resolver: Callable | None = None
    is_list: bool = False
    is_non_null: bool = False
    deprecation_reason: str | None = None


@dataclass
class GraphQLArgument:
    """Definition of a GraphQL argument."""
    name: str
    type_name: str
    description: str | None = None
    default_value: Any | None = None
    is_required: bool = False


@dataclass
class GraphQLType:
    """Definition of a GraphQL type."""
    name: str
    kind: GraphQLTypeKind
    description: str | None = None
    fields: dict[str, GraphQLField] = field(default_factory=dict)
    interfaces: list[str] = field(default_factory=list)
    enum_values: list[str] = field(default_factory=list)
    input_fields: dict[str, GraphQLArgument] = field(default_factory=dict)


@dataclass
class GraphQLDirective:
    """Definition of a GraphQL directive."""
    name: str
    description: str | None = None
    locations: list[str] = field(default_factory=list)
    args: dict[str, GraphQLArgument] = field(default_factory=dict)


# =============================================================================
# Schema Builder
# =============================================================================


class GraphQLSchemaBuilder:
    """Builder for GraphQL schema definitions."""

    def __init__(self):
        self._types: dict[str, GraphQLType] = {}
        self._directives: dict[str, GraphQLDirective] = {}
        self._query_type: str | None = None
        self._mutation_type: str | None = None
        self._subscription_type: str | None = None
        self._register_builtin_scalars()

    def _register_builtin_scalars(self):
        """Register built-in GraphQL scalar types."""
        scalars = ["String", "Int", "Float", "Boolean", "ID"]
        for scalar in scalars:
            self._types[scalar] = GraphQLType(
                name=scalar,
                kind=GraphQLTypeKind.SCALAR,
                description=f"Built-in {scalar} scalar"
            )
        # Add custom scalars
        self._types["DateTime"] = GraphQLType(
            name="DateTime",
            kind=GraphQLTypeKind.SCALAR,
            description="ISO 8601 date-time string"
        )
        self._types["JSON"] = GraphQLType(
            name="JSON",
            kind=GraphQLTypeKind.SCALAR,
            description="Arbitrary JSON value"
        )

    def add_type(self, type_def: GraphQLType) -> "GraphQLSchemaBuilder":
        """Add a type to the schema."""
        self._types[type_def.name] = type_def
        return self

    def add_enum(
        self,
        name: str,
        values: list[str],
        description: str | None = None
    ) -> "GraphQLSchemaBuilder":
        """Add an enum type to the schema."""
        self._types[name] = GraphQLType(
            name=name,
            kind=GraphQLTypeKind.ENUM,
            description=description,
            enum_values=values
        )
        return self

    def add_interface(
        self,
        name: str,
        fields: dict[str, GraphQLField],
        description: str | None = None
    ) -> "GraphQLSchemaBuilder":
        """Add an interface type to the schema."""
        self._types[name] = GraphQLType(
            name=name,
            kind=GraphQLTypeKind.INTERFACE,
            description=description,
            fields=fields
        )
        return self

    def add_object_type(
        self,
        name: str,
        fields: dict[str, GraphQLField],
        description: str | None = None,
        interfaces: list[str | None] = None
    ) -> "GraphQLSchemaBuilder":
        """Add an object type to the schema."""
        self._types[name] = GraphQLType(
            name=name,
            kind=GraphQLTypeKind.OBJECT,
            description=description,
            fields=fields,
            interfaces=interfaces or []
        )
        return self

    def add_input_type(
        self,
        name: str,
        fields: dict[str, GraphQLArgument],
        description: str | None = None
    ) -> "GraphQLSchemaBuilder":
        """Add an input type to the schema."""
        self._types[name] = GraphQLType(
            name=name,
            kind=GraphQLTypeKind.INPUT_OBJECT,
            description=description,
            input_fields=fields
        )
        return self

    def add_directive(self, directive: GraphQLDirective) -> "GraphQLSchemaBuilder":
        """Add a directive to the schema."""
        self._directives[directive.name] = directive
        return self

    def set_query_type(self, name: str) -> "GraphQLSchemaBuilder":
        """Set the query type name."""
        self._query_type = name
        return self

    def set_mutation_type(self, name: str) -> "GraphQLSchemaBuilder":
        """Set the mutation type name."""
        self._mutation_type = name
        return self

    def set_subscription_type(self, name: str) -> "GraphQLSchemaBuilder":
        """Set the subscription type name."""
        self._subscription_type = name
        return self

    def build(self) -> "GraphQLSchema":
        """Build the schema."""
        return GraphQLSchema(
            types=dict(self._types),
            directives=dict(self._directives),
            query_type=self._query_type,
            mutation_type=self._mutation_type,
            subscription_type=self._subscription_type
        )


# =============================================================================
# Schema
# =============================================================================


@dataclass
class GraphQLSchema:
    """GraphQL schema definition."""
    types: dict[str, GraphQLType]
    directives: dict[str, GraphQLDirective]
    query_type: str | None
    mutation_type: str | None
    subscription_type: str | None

    def get_type(self, name: str) -> GraphQLType | None:
        """Get a type by name."""
        return self.types.get(name)

    def get_query_type(self) -> GraphQLType | None:
        """Get the query type."""
        if self.query_type:
            return self.types.get(self.query_type)
        return None

    def get_mutation_type(self) -> GraphQLType | None:
        """Get the mutation type."""
        if self.mutation_type:
            return self.types.get(self.mutation_type)
        return None

    def validate(self) -> list[str]:
        """Validate the schema and return any errors."""
        errors = []
        if not self.query_type:
            errors.append("Schema must have a query type")
        if self.query_type and self.query_type not in self.types:
            errors.append(f"Query type '{self.query_type}' not found")
        if self.mutation_type and self.mutation_type not in self.types:
            errors.append(f"Mutation type '{self.mutation_type}' not found")
        return errors

    def to_sdl(self) -> str:
        """Convert schema to SDL (Schema Definition Language)."""
        lines = []

        # Schema definition
        lines.append("schema {")
        if self.query_type:
            lines.append(f"  query: {self.query_type}")
        if self.mutation_type:
            lines.append(f"  mutation: {self.mutation_type}")
        if self.subscription_type:
            lines.append(f"  subscription: {self.subscription_type}")
        lines.append("}")
        lines.append("")

        # Custom scalars
        for type_def in self.types.values():
            if type_def.kind == GraphQLTypeKind.SCALAR:
                if type_def.name not in ["String", "Int", "Float", "Boolean", "ID"]:
                    if type_def.description:
                        lines.append(f'"""{type_def.description}"""')
                    lines.append(f"scalar {type_def.name}")
                    lines.append("")

        # Enums
        for type_def in self.types.values():
            if type_def.kind == GraphQLTypeKind.ENUM:
                if type_def.description:
                    lines.append(f'"""{type_def.description}"""')
                lines.append(f"enum {type_def.name} {{")
                for value in type_def.enum_values:
                    lines.append(f"  {value}")
                lines.append("}")
                lines.append("")

        # Interfaces
        for type_def in self.types.values():
            if type_def.kind == GraphQLTypeKind.INTERFACE:
                if type_def.description:
                    lines.append(f'"""{type_def.description}"""')
                lines.append(f"interface {type_def.name} {{")
                for field in type_def.fields.values():
                    field_type = field.type_name
                    if field.is_list:
                        field_type = f"[{field_type}]"
                    if field.is_non_null:
                        field_type = f"{field_type}!"
                    lines.append(f"  {field.name}: {field_type}")
                lines.append("}")
                lines.append("")

        # Input types
        for type_def in self.types.values():
            if type_def.kind == GraphQLTypeKind.INPUT_OBJECT:
                if type_def.description:
                    lines.append(f'"""{type_def.description}"""')
                lines.append(f"input {type_def.name} {{")
                for arg in type_def.input_fields.values():
                    arg_type = arg.type_name
                    if arg.is_required:
                        arg_type = f"{arg_type}!"
                    if arg.default_value is not None:
                        lines.append(f"  {arg.name}: {arg_type} = {json.dumps(arg.default_value)}")
                    else:
                        lines.append(f"  {arg.name}: {arg_type}")
                lines.append("}")
                lines.append("")

        # Object types
        for type_def in self.types.values():
            if type_def.kind == GraphQLTypeKind.OBJECT:
                if type_def.description:
                    lines.append(f'"""{type_def.description}"""')
                implements = ""
                if type_def.interfaces:
                    implements = f" implements {' & '.join(type_def.interfaces)}"
                lines.append(f"type {type_def.name}{implements} {{")
                for field in type_def.fields.values():
                    field_type = field.type_name
                    if field.is_list:
                        field_type = f"[{field_type}]"
                    if field.is_non_null:
                        field_type = f"{field_type}!"

                    # Field arguments
                    args_str = ""
                    if field.args:
                        arg_parts = []
                        for arg in field.args.values():
                            arg_type = arg.type_name
                            if arg.is_required:
                                arg_type = f"{arg_type}!"
                            arg_parts.append(f"{arg.name}: {arg_type}")
                        args_str = f"({', '.join(arg_parts)})"

                    deprecation = ""
                    if field.deprecation_reason:
                        deprecation = f' @deprecated(reason: "{field.deprecation_reason}")'

                    if field.description:
                        lines.append(f'  """{field.description}"""')
                    lines.append(f"  {field.name}{args_str}: {field_type}{deprecation}")
                lines.append("}")
                lines.append("")

        return "\n".join(lines)


# =============================================================================
# Query Parser
# =============================================================================


@dataclass
class GraphQLSelection:
    """A selection in a GraphQL query."""
    field_name: str
    alias: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    selections: list["GraphQLSelection"] = field(default_factory=list)
    directives: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GraphQLOperation:
    """A GraphQL operation (query, mutation, subscription)."""
    operation_type: str  # query, mutation, subscription
    name: str | None
    variables: dict[str, dict[str, Any]]  # name -> {type, default}
    selections: list[GraphQLSelection]
    directives: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GraphQLDocument:
    """A parsed GraphQL document."""
    operations: list[GraphQLOperation]
    fragments: dict[str, list[GraphQLSelection]]


class GraphQLParser:
    """Simple GraphQL query parser."""

    def __init__(self):
        self._pos = 0
        self._text = ""

    def parse(self, query: str) -> GraphQLDocument:
        """Parse a GraphQL query string."""
        self._text = query.strip()
        self._pos = 0

        operations = []
        fragments = {}

        while self._pos < len(self._text):
            self._skip_whitespace_and_comments()
            if self._pos >= len(self._text):
                break

            if self._peek_word() == "fragment":
                name, selections = self._parse_fragment()
                fragments[name] = selections
            else:
                operation = self._parse_operation()
                operations.append(operation)

            self._skip_whitespace_and_comments()

        return GraphQLDocument(operations=operations, fragments=fragments)

    def _skip_whitespace_and_comments(self):
        """Skip whitespace and comments."""
        while self._pos < len(self._text):
            if self._text[self._pos].isspace():
                self._pos += 1
            elif self._text[self._pos] == "#":
                while self._pos < len(self._text) and self._text[self._pos] != "\n":
                    self._pos += 1
            else:
                break

    def _peek_word(self) -> str:
        """Peek at the next word without consuming."""
        self._skip_whitespace_and_comments()
        start = self._pos
        while self._pos < len(self._text) and (self._text[self._pos].isalnum() or self._text[self._pos] == "_"):
            self._pos += 1
        word = self._text[start:self._pos]
        self._pos = start
        return word

    def _read_word(self) -> str:
        """Read a word."""
        self._skip_whitespace_and_comments()
        start = self._pos
        while self._pos < len(self._text) and (self._text[self._pos].isalnum() or self._text[self._pos] == "_"):
            self._pos += 1
        return self._text[start:self._pos]

    def _expect(self, char: str):
        """Expect a specific character."""
        self._skip_whitespace_and_comments()
        if self._pos >= len(self._text) or self._text[self._pos] != char:
            raise ValueError(f"Expected '{char}' at position {self._pos}")
        self._pos += 1

    def _parse_operation(self) -> GraphQLOperation:
        """Parse an operation."""
        self._skip_whitespace_and_comments()

        # Check for operation type
        operation_type = "query"
        name = None
        variables = {}

        word = self._peek_word()
        if word in ("query", "mutation", "subscription"):
            operation_type = self._read_word()
            self._skip_whitespace_and_comments()

            # Optional operation name
            if self._pos < len(self._text) and (self._text[self._pos].isalpha() or self._text[self._pos] == "_"):
                name = self._read_word()

            # Optional variables
            self._skip_whitespace_and_comments()
            if self._pos < len(self._text) and self._text[self._pos] == "(":
                variables = self._parse_variables()

        # Selection set
        selections = self._parse_selection_set()

        return GraphQLOperation(
            operation_type=operation_type,
            name=name,
            variables=variables,
            selections=selections
        )

    def _parse_variables(self) -> dict[str, dict[str, Any]]:
        """Parse variable definitions."""
        self._expect("(")
        variables = {}

        while True:
            self._skip_whitespace_and_comments()
            if self._text[self._pos] == ")":
                break

            self._expect("$")
            var_name = self._read_word()
            self._expect(":")
            var_type = self._read_word()

            # Check for non-null
            self._skip_whitespace_and_comments()
            if self._pos < len(self._text) and self._text[self._pos] == "!":
                var_type += "!"
                self._pos += 1

            # Check for default value
            default_value = None
            self._skip_whitespace_and_comments()
            if self._pos < len(self._text) and self._text[self._pos] == "=":
                self._pos += 1
                default_value = self._parse_value()

            variables[var_name] = {"type": var_type, "default": default_value}

            self._skip_whitespace_and_comments()
            if self._text[self._pos] == ",":
                self._pos += 1

        self._expect(")")
        return variables

    def _parse_selection_set(self) -> list[GraphQLSelection]:
        """Parse a selection set."""
        self._expect("{")
        selections = []

        while True:
            self._skip_whitespace_and_comments()
            if self._text[self._pos] == "}":
                break

            selection = self._parse_selection()
            selections.append(selection)

        self._expect("}")
        return selections

    def _parse_selection(self) -> GraphQLSelection:
        """Parse a single selection."""
        self._skip_whitespace_and_comments()

        # Check for fragment spread
        if self._text[self._pos:self._pos + 3] == "...":
            self._pos += 3
            fragment_name = self._read_word()
            return GraphQLSelection(field_name=f"...{fragment_name}")

        # Parse field
        field_name = self._read_word()
        alias = None

        # Check for alias
        self._skip_whitespace_and_comments()
        if self._pos < len(self._text) and self._text[self._pos] == ":":
            self._pos += 1
            alias = field_name
            field_name = self._read_word()

        # Parse arguments
        arguments = {}
        self._skip_whitespace_and_comments()
        if self._pos < len(self._text) and self._text[self._pos] == "(":
            arguments = self._parse_arguments()

        # Parse nested selection set
        selections = []
        self._skip_whitespace_and_comments()
        if self._pos < len(self._text) and self._text[self._pos] == "{":
            selections = self._parse_selection_set()

        return GraphQLSelection(
            field_name=field_name,
            alias=alias,
            arguments=arguments,
            selections=selections
        )

    def _parse_arguments(self) -> dict[str, Any]:
        """Parse arguments."""
        self._expect("(")
        arguments = {}

        while True:
            self._skip_whitespace_and_comments()
            if self._text[self._pos] == ")":
                break

            arg_name = self._read_word()
            self._expect(":")
            arg_value = self._parse_value()
            arguments[arg_name] = arg_value

            self._skip_whitespace_and_comments()
            if self._text[self._pos] == ",":
                self._pos += 1

        self._expect(")")
        return arguments

    def _parse_value(self) -> Any:
        """Parse a value."""
        self._skip_whitespace_and_comments()

        if self._text[self._pos] == "$":
            # Variable reference
            self._pos += 1
            return {"$var": self._read_word()}
        elif self._text[self._pos] == '"':
            # String
            return self._parse_string()
        elif self._text[self._pos] == "[":
            # List
            return self._parse_list()
        elif self._text[self._pos] == "{":
            # Object
            return self._parse_object()
        elif self._text[self._pos:self._pos + 4] == "true":
            self._pos += 4
            return True
        elif self._text[self._pos:self._pos + 5] == "false":
            self._pos += 5
            return False
        elif self._text[self._pos:self._pos + 4] == "null":
            self._pos += 4
            return None
        elif self._text[self._pos].isdigit() or self._text[self._pos] == "-":
            return self._parse_number()
        else:
            # Enum value
            return self._read_word()

    def _parse_string(self) -> str:
        """Parse a string value."""
        self._expect('"')
        start = self._pos
        while self._pos < len(self._text) and self._text[self._pos] != '"':
            if self._text[self._pos] == "\\":
                self._pos += 2
            else:
                self._pos += 1
        value = self._text[start:self._pos]
        self._expect('"')
        return value

    def _parse_number(self) -> int | float:
        """Parse a number value."""
        start = self._pos
        if self._text[self._pos] == "-":
            self._pos += 1
        while self._pos < len(self._text) and self._text[self._pos].isdigit():
            self._pos += 1
        if self._pos < len(self._text) and self._text[self._pos] == ".":
            self._pos += 1
            while self._pos < len(self._text) and self._text[self._pos].isdigit():
                self._pos += 1
            return float(self._text[start:self._pos])
        return int(self._text[start:self._pos])

    def _parse_list(self) -> list[Any]:
        """Parse a list value."""
        self._expect("[")
        items = []
        while True:
            self._skip_whitespace_and_comments()
            if self._text[self._pos] == "]":
                break
            items.append(self._parse_value())
            self._skip_whitespace_and_comments()
            if self._text[self._pos] == ",":
                self._pos += 1
        self._expect("]")
        return items

    def _parse_object(self) -> dict[str, Any]:
        """Parse an object value."""
        self._expect("{")
        obj = {}
        while True:
            self._skip_whitespace_and_comments()
            if self._text[self._pos] == "}":
                break
            key = self._read_word()
            self._expect(":")
            value = self._parse_value()
            obj[key] = value
            self._skip_whitespace_and_comments()
            if self._text[self._pos] == ",":
                self._pos += 1
        self._expect("}")
        return obj

    def _parse_fragment(self) -> tuple[str, list[GraphQLSelection]]:
        """Parse a fragment definition."""
        self._read_word()  # "fragment"
        name = self._read_word()
        self._read_word()  # "on"
        self._read_word()  # type name
        selections = self._parse_selection_set()
        return name, selections


# =============================================================================
# Query Executor
# =============================================================================


@dataclass
class GraphQLResult:
    """Result of a GraphQL query execution."""
    data: dict[str, Any | None] = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        if self.data is not None:
            result["data"] = self.data
        if self.errors:
            result["errors"] = self.errors
        if self.extensions:
            result["extensions"] = self.extensions
        return result


@dataclass
class ExecutionContext:
    """Context for query execution."""
    schema: GraphQLSchema
    document: GraphQLDocument
    variables: dict[str, Any]
    operation_name: str | None
    root_value: Any
    context: dict[str, Any]
    fragments: dict[str, list[GraphQLSelection]]
    errors: list[dict[str, Any]] = field(default_factory=list)


class GraphQLExecutor:
    """Executes GraphQL queries against a schema."""

    def __init__(self, schema: GraphQLSchema):
        self.schema = schema
        self._resolvers: dict[str, dict[str, Callable]] = {}

    def register_resolver(
        self,
        type_name: str,
        field_name: str,
        resolver: Callable
    ):
        """Register a resolver for a field."""
        if type_name not in self._resolvers:
            self._resolvers[type_name] = {}
        self._resolvers[type_name][field_name] = resolver

    def execute(
        self,
        query: str,
        variables: dict[str, Any | None] = None,
        operation_name: str | None = None,
        root_value: Any = None,
        context: dict[str, Any | None] = None
    ) -> GraphQLResult:
        """Execute a GraphQL query."""
        try:
            # Parse the query
            parser = GraphQLParser()
            document = parser.parse(query)

            if not document.operations:
                return GraphQLResult(errors=[{"message": "No operation found in query"}])

            # Find the operation to execute
            operation = None
            if operation_name:
                for op in document.operations:
                    if op.name == operation_name:
                        operation = op
                        break
                if not operation:
                    return GraphQLResult(
                        errors=[{"message": f"Operation '{operation_name}' not found"}]
                    )
            else:
                if len(document.operations) > 1:
                    return GraphQLResult(
                        errors=[{"message": "Multiple operations found, operation_name required"}]
                    )
                operation = document.operations[0]

            # Create execution context
            exec_context = ExecutionContext(
                schema=self.schema,
                document=document,
                variables=variables or {},
                operation_name=operation_name,
                root_value=root_value or {},
                context=context or {},
                fragments=document.fragments
            )

            # Execute the operation
            data = self._execute_operation(operation, exec_context)

            return GraphQLResult(
                data=data,
                errors=exec_context.errors if exec_context.errors else []
            )
        except Exception as e:
            return GraphQLResult(errors=[{"message": str(e)}])

    def _execute_operation(
        self,
        operation: GraphQLOperation,
        context: ExecutionContext
    ) -> dict[str, Any]:
        """Execute an operation."""
        # Get the root type
        if operation.operation_type == "query":
            root_type = self.schema.get_query_type()
        elif operation.operation_type == "mutation":
            root_type = self.schema.get_mutation_type()
        else:
            context.errors.append(
                {"message": f"Unsupported operation type: {operation.operation_type}"}
            )
            return {}

        if not root_type:
            context.errors.append(
                {"message": f"No {operation.operation_type} type defined"}
            )
            return {}

        # Execute selection set
        return self._execute_selection_set(
            root_type.name,
            operation.selections,
            context.root_value,
            context
        )

    def _execute_selection_set(
        self,
        type_name: str,
        selections: list[GraphQLSelection],
        parent_value: Any,
        context: ExecutionContext
    ) -> dict[str, Any]:
        """Execute a selection set."""
        result = {}

        for selection in selections:
            # Handle fragment spread
            if selection.field_name.startswith("..."):
                fragment_name = selection.field_name[3:]
                if fragment_name in context.fragments:
                    fragment_result = self._execute_selection_set(
                        type_name,
                        context.fragments[fragment_name],
                        parent_value,
                        context
                    )
                    result.update(fragment_result)
                continue

            # Get the field
            field_name = selection.field_name
            result_key = selection.alias or field_name

            # Resolve field value
            value = self._resolve_field(
                type_name,
                field_name,
                selection.arguments,
                parent_value,
                context
            )

            # Handle nested selections
            if selection.selections and value is not None:
                field_type = self._get_field_type(type_name, field_name)
                if isinstance(value, list):
                    value = [
                        self._execute_selection_set(
                            field_type,
                            selection.selections,
                            item,
                            context
                        )
                        for item in value
                    ]
                else:
                    value = self._execute_selection_set(
                        field_type,
                        selection.selections,
                        value,
                        context
                    )

            result[result_key] = value

        return result

    def _resolve_field(
        self,
        type_name: str,
        field_name: str,
        arguments: dict[str, Any],
        parent_value: Any,
        context: ExecutionContext
    ) -> Any:
        """Resolve a field value."""
        # Resolve variable references in arguments
        resolved_args = {}
        for key, value in arguments.items():
            if isinstance(value, dict) and "$var" in value:
                var_name = value["$var"]
                resolved_args[key] = context.variables.get(var_name)
            else:
                resolved_args[key] = value

        # Try to find a resolver
        if type_name in self._resolvers and field_name in self._resolvers[type_name]:
            resolver = self._resolvers[type_name][field_name]
            try:
                return resolver(parent_value, resolved_args, context.context)
            except Exception as e:
                context.errors.append({
                    "message": str(e),
                    "path": [field_name]
                })
                return None

        # Default resolver: look for field in parent value
        if isinstance(parent_value, dict):
            return parent_value.get(field_name)
        elif hasattr(parent_value, field_name):
            return getattr(parent_value, field_name)

        return None

    def _get_field_type(self, type_name: str, field_name: str) -> str:
        """Get the type of a field."""
        type_def = self.schema.get_type(type_name)
        if type_def and type_def.fields:
            field = type_def.fields.get(field_name)
            if field:
                return field.type_name
        return "String"


# =============================================================================
# KG Schema Factory
# =============================================================================


def create_kg_graphql_schema() -> GraphQLSchema:
    """Create the Knowledge Graph GraphQL schema."""
    builder = GraphQLSchemaBuilder()

    # Add enums
    builder.add_enum(
        "SemanticGroup",
        [g.name for g in SemanticGroupEnum],
        "UMLS semantic groups"
    )

    builder.add_enum(
        "RelationshipType",
        [r.name for r in RelationshipTypeEnum],
        "Knowledge graph relationship types"
    )

    builder.add_enum(
        "ReasoningStrategy",
        ["BREADTH_FIRST", "DEPTH_FIRST", "BIDIRECTIONAL", "WEIGHTED"],
        "Reasoning strategies for path finding"
    )

    # Add interfaces
    builder.add_interface(
        "Node",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "createdAt": GraphQLField(name="createdAt", type_name="DateTime"),
            "updatedAt": GraphQLField(name="updatedAt", type_name="DateTime"),
        },
        "Common interface for all graph nodes"
    )

    # Add input types
    builder.add_input_type(
        "ConceptSearchInput",
        {
            "query": GraphQLArgument(name="query", type_name="String", is_required=True),
            "semanticGroups": GraphQLArgument(name="semanticGroups", type_name="[SemanticGroup]"),
            "limit": GraphQLArgument(name="limit", type_name="Int", default_value=20),
            "offset": GraphQLArgument(name="offset", type_name="Int", default_value=0),
        },
        "Input for searching concepts"
    )

    builder.add_input_type(
        "PathFindingInput",
        {
            "sourceCui": GraphQLArgument(name="sourceCui", type_name="String", is_required=True),
            "targetCui": GraphQLArgument(name="targetCui", type_name="String", is_required=True),
            "maxHops": GraphQLArgument(name="maxHops", type_name="Int", default_value=3),
            "relationshipTypes": GraphQLArgument(name="relationshipTypes", type_name="[RelationshipType]"),
            "strategy": GraphQLArgument(name="strategy", type_name="ReasoningStrategy", default_value="BREADTH_FIRST"),
        },
        "Input for finding paths between concepts"
    )

    builder.add_input_type(
        "TemporalFilterInput",
        {
            "validFrom": GraphQLArgument(name="validFrom", type_name="DateTime"),
            "validTo": GraphQLArgument(name="validTo", type_name="DateTime"),
            "asOfTime": GraphQLArgument(name="asOfTime", type_name="DateTime"),
        },
        "Input for temporal filtering"
    )

    # Add object types
    builder.add_object_type(
        "Concept",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True, description="Unique identifier"),
            "cui": GraphQLField(name="cui", type_name="String", is_non_null=True, description="UMLS CUI"),
            "preferredName": GraphQLField(name="preferredName", type_name="String", is_non_null=True, description="Preferred name"),
            "definitions": GraphQLField(name="definitions", type_name="String", is_list=True, description="Concept definitions"),
            "semanticTypes": GraphQLField(name="semanticTypes", type_name="String", is_list=True, description="Semantic types"),
            "semanticGroup": GraphQLField(name="semanticGroup", type_name="SemanticGroup", description="Semantic group"),
            "vocabularies": GraphQLField(name="vocabularies", type_name="String", is_list=True, description="Source vocabularies"),
            "synonyms": GraphQLField(name="synonyms", type_name="String", is_list=True, description="Synonyms"),
            "relationships": GraphQLField(
                name="relationships",
                type_name="Relationship",
                is_list=True,
                description="Related concepts",
                args={
                    "types": GraphQLArgument(name="types", type_name="[RelationshipType]"),
                    "limit": GraphQLArgument(name="limit", type_name="Int", default_value=50),
                }
            ),
            "parents": GraphQLField(name="parents", type_name="Concept", is_list=True, description="Parent concepts (IS_A)"),
            "children": GraphQLField(name="children", type_name="Concept", is_list=True, description="Child concepts"),
            "embedding": GraphQLField(name="embedding", type_name="[Float]", description="Vector embedding"),
            "createdAt": GraphQLField(name="createdAt", type_name="DateTime"),
            "updatedAt": GraphQLField(name="updatedAt", type_name="DateTime"),
        },
        "A medical concept from UMLS",
        interfaces=["Node"]
    )

    builder.add_object_type(
        "Relationship",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "type": GraphQLField(name="type", type_name="RelationshipType", is_non_null=True),
            "source": GraphQLField(name="source", type_name="Concept", is_non_null=True),
            "target": GraphQLField(name="target", type_name="Concept", is_non_null=True),
            "weight": GraphQLField(name="weight", type_name="Float"),
            "evidence": GraphQLField(name="evidence", type_name="String", is_list=True),
            "confidence": GraphQLField(name="confidence", type_name="Float"),
            "validFrom": GraphQLField(name="validFrom", type_name="DateTime"),
            "validTo": GraphQLField(name="validTo", type_name="DateTime"),
        },
        "A relationship between concepts"
    )

    builder.add_object_type(
        "ReasoningPath",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "source": GraphQLField(name="source", type_name="Concept", is_non_null=True),
            "target": GraphQLField(name="target", type_name="Concept", is_non_null=True),
            "steps": GraphQLField(name="steps", type_name="PathStep", is_list=True, is_non_null=True),
            "totalScore": GraphQLField(name="totalScore", type_name="Float"),
            "hopCount": GraphQLField(name="hopCount", type_name="Int"),
            "explanation": GraphQLField(name="explanation", type_name="String"),
        },
        "A reasoning path between concepts"
    )

    builder.add_object_type(
        "PathStep",
        {
            "order": GraphQLField(name="order", type_name="Int", is_non_null=True),
            "concept": GraphQLField(name="concept", type_name="Concept", is_non_null=True),
            "relationship": GraphQLField(name="relationship", type_name="Relationship"),
            "score": GraphQLField(name="score", type_name="Float"),
        },
        "A step in a reasoning path"
    )

    builder.add_object_type(
        "Patient",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "mrn": GraphQLField(name="mrn", type_name="String"),
            "diagnoses": GraphQLField(
                name="diagnoses",
                type_name="Diagnosis",
                is_list=True,
                args={
                    "active": GraphQLArgument(name="active", type_name="Boolean"),
                    "temporal": GraphQLArgument(name="temporal", type_name="TemporalFilterInput"),
                }
            ),
            "medications": GraphQLField(
                name="medications",
                type_name="Medication",
                is_list=True,
                args={
                    "active": GraphQLArgument(name="active", type_name="Boolean"),
                }
            ),
            "labs": GraphQLField(
                name="labs",
                type_name="LabResult",
                is_list=True,
                args={
                    "limit": GraphQLArgument(name="limit", type_name="Int", default_value=100),
                }
            ),
            "graph": GraphQLField(name="graph", type_name="PatientGraph", description="Patient knowledge graph"),
            "timeline": GraphQLField(name="timeline", type_name="TimelineEvent", is_list=True),
        },
        "A patient with clinical data",
        interfaces=["Node"]
    )

    builder.add_object_type(
        "Diagnosis",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "concept": GraphQLField(name="concept", type_name="Concept", is_non_null=True),
            "code": GraphQLField(name="code", type_name="String"),
            "codeSystem": GraphQLField(name="codeSystem", type_name="String"),
            "displayName": GraphQLField(name="displayName", type_name="String"),
            "status": GraphQLField(name="status", type_name="String"),
            "onsetDate": GraphQLField(name="onsetDate", type_name="DateTime"),
            "resolvedDate": GraphQLField(name="resolvedDate", type_name="DateTime"),
            "isPrimary": GraphQLField(name="isPrimary", type_name="Boolean"),
        },
        "A patient diagnosis"
    )

    builder.add_object_type(
        "Medication",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "concept": GraphQLField(name="concept", type_name="Concept"),
            "rxcui": GraphQLField(name="rxcui", type_name="String"),
            "name": GraphQLField(name="name", type_name="String", is_non_null=True),
            "dose": GraphQLField(name="dose", type_name="String"),
            "route": GraphQLField(name="route", type_name="String"),
            "frequency": GraphQLField(name="frequency", type_name="String"),
            "status": GraphQLField(name="status", type_name="String"),
            "startDate": GraphQLField(name="startDate", type_name="DateTime"),
            "endDate": GraphQLField(name="endDate", type_name="DateTime"),
            "interactions": GraphQLField(name="interactions", type_name="DrugInteraction", is_list=True),
        },
        "A patient medication"
    )

    builder.add_object_type(
        "DrugInteraction",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "drug1": GraphQLField(name="drug1", type_name="Medication", is_non_null=True),
            "drug2": GraphQLField(name="drug2", type_name="Medication", is_non_null=True),
            "severity": GraphQLField(name="severity", type_name="String"),
            "description": GraphQLField(name="description", type_name="String"),
            "clinicalEffect": GraphQLField(name="clinicalEffect", type_name="String"),
            "management": GraphQLField(name="management", type_name="String"),
        },
        "A drug-drug interaction"
    )

    builder.add_object_type(
        "LabResult",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "concept": GraphQLField(name="concept", type_name="Concept"),
            "loincCode": GraphQLField(name="loincCode", type_name="String"),
            "name": GraphQLField(name="name", type_name="String", is_non_null=True),
            "value": GraphQLField(name="value", type_name="String"),
            "unit": GraphQLField(name="unit", type_name="String"),
            "referenceRange": GraphQLField(name="referenceRange", type_name="String"),
            "interpretation": GraphQLField(name="interpretation", type_name="String"),
            "collectionDate": GraphQLField(name="collectionDate", type_name="DateTime"),
        },
        "A laboratory result"
    )

    builder.add_object_type(
        "PatientGraph",
        {
            "nodes": GraphQLField(name="nodes", type_name="GraphNode", is_list=True, is_non_null=True),
            "edges": GraphQLField(name="edges", type_name="GraphEdge", is_list=True, is_non_null=True),
            "clusters": GraphQLField(name="clusters", type_name="GraphCluster", is_list=True),
        },
        "A patient's knowledge graph"
    )

    builder.add_object_type(
        "GraphNode",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "label": GraphQLField(name="label", type_name="String", is_non_null=True),
            "type": GraphQLField(name="type", type_name="String"),
            "properties": GraphQLField(name="properties", type_name="JSON"),
        },
        "A node in a graph visualization"
    )

    builder.add_object_type(
        "GraphEdge",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "source": GraphQLField(name="source", type_name="ID", is_non_null=True),
            "target": GraphQLField(name="target", type_name="ID", is_non_null=True),
            "type": GraphQLField(name="type", type_name="String"),
            "weight": GraphQLField(name="weight", type_name="Float"),
        },
        "An edge in a graph visualization"
    )

    builder.add_object_type(
        "GraphCluster",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "label": GraphQLField(name="label", type_name="String"),
            "nodeIds": GraphQLField(name="nodeIds", type_name="ID", is_list=True, is_non_null=True),
        },
        "A cluster of nodes in a graph"
    )

    builder.add_object_type(
        "TimelineEvent",
        {
            "id": GraphQLField(name="id", type_name="ID", is_non_null=True),
            "timestamp": GraphQLField(name="timestamp", type_name="DateTime", is_non_null=True),
            "type": GraphQLField(name="type", type_name="String", is_non_null=True),
            "title": GraphQLField(name="title", type_name="String", is_non_null=True),
            "description": GraphQLField(name="description", type_name="String"),
            "concept": GraphQLField(name="concept", type_name="Concept"),
        },
        "An event in a patient's timeline"
    )

    builder.add_object_type(
        "ConceptSearchResult",
        {
            "concepts": GraphQLField(name="concepts", type_name="Concept", is_list=True, is_non_null=True),
            "totalCount": GraphQLField(name="totalCount", type_name="Int", is_non_null=True),
            "hasMore": GraphQLField(name="hasMore", type_name="Boolean", is_non_null=True),
        },
        "Result of a concept search"
    )

    builder.add_object_type(
        "PathFindingResult",
        {
            "paths": GraphQLField(name="paths", type_name="ReasoningPath", is_list=True, is_non_null=True),
            "totalPaths": GraphQLField(name="totalPaths", type_name="Int", is_non_null=True),
            "searchTime": GraphQLField(name="searchTime", type_name="Float"),
            "strategy": GraphQLField(name="strategy", type_name="ReasoningStrategy"),
        },
        "Result of path finding"
    )

    # Add query type
    builder.add_object_type(
        "Query",
        {
            "concept": GraphQLField(
                name="concept",
                type_name="Concept",
                description="Get a concept by CUI",
                args={
                    "cui": GraphQLArgument(name="cui", type_name="String", is_required=True),
                }
            ),
            "concepts": GraphQLField(
                name="concepts",
                type_name="Concept",
                is_list=True,
                description="Get multiple concepts by CUI",
                args={
                    "cuis": GraphQLArgument(name="cuis", type_name="[String]", is_required=True),
                }
            ),
            "searchConcepts": GraphQLField(
                name="searchConcepts",
                type_name="ConceptSearchResult",
                is_non_null=True,
                description="Search for concepts",
                args={
                    "input": GraphQLArgument(name="input", type_name="ConceptSearchInput", is_required=True),
                }
            ),
            "findPaths": GraphQLField(
                name="findPaths",
                type_name="PathFindingResult",
                is_non_null=True,
                description="Find reasoning paths between concepts",
                args={
                    "input": GraphQLArgument(name="input", type_name="PathFindingInput", is_required=True),
                }
            ),
            "patient": GraphQLField(
                name="patient",
                type_name="Patient",
                description="Get a patient by ID",
                args={
                    "id": GraphQLArgument(name="id", type_name="ID", is_required=True),
                }
            ),
            "similarPatients": GraphQLField(
                name="similarPatients",
                type_name="Patient",
                is_list=True,
                description="Find patients similar to a given patient",
                args={
                    "patientId": GraphQLArgument(name="patientId", type_name="ID", is_required=True),
                    "limit": GraphQLArgument(name="limit", type_name="Int", default_value=10),
                }
            ),
            "drugInteractions": GraphQLField(
                name="drugInteractions",
                type_name="DrugInteraction",
                is_list=True,
                description="Check for drug interactions",
                args={
                    "rxcuis": GraphQLArgument(name="rxcuis", type_name="[String]", is_required=True),
                }
            ),
        },
        "Root query type"
    )

    # Add mutation type
    builder.add_object_type(
        "Mutation",
        {
            "addConcept": GraphQLField(
                name="addConcept",
                type_name="Concept",
                description="Add a new concept (admin only)",
                args={
                    "cui": GraphQLArgument(name="cui", type_name="String", is_required=True),
                    "preferredName": GraphQLArgument(name="preferredName", type_name="String", is_required=True),
                    "semanticGroup": GraphQLArgument(name="semanticGroup", type_name="SemanticGroup"),
                }
            ),
            "addRelationship": GraphQLField(
                name="addRelationship",
                type_name="Relationship",
                description="Add a relationship between concepts",
                args={
                    "sourceCui": GraphQLArgument(name="sourceCui", type_name="String", is_required=True),
                    "targetCui": GraphQLArgument(name="targetCui", type_name="String", is_required=True),
                    "type": GraphQLArgument(name="type", type_name="RelationshipType", is_required=True),
                    "weight": GraphQLArgument(name="weight", type_name="Float"),
                }
            ),
            "updateConceptEmbedding": GraphQLField(
                name="updateConceptEmbedding",
                type_name="Concept",
                description="Update a concept's embedding",
                args={
                    "cui": GraphQLArgument(name="cui", type_name="String", is_required=True),
                    "embedding": GraphQLArgument(name="embedding", type_name="[Float]", is_required=True),
                }
            ),
        },
        "Root mutation type"
    )

    builder.set_query_type("Query")
    builder.set_mutation_type("Mutation")

    return builder.build()


# =============================================================================
# KG GraphQL Service
# =============================================================================


class MockKGDataSource:
    """Mock data source for testing."""

    def __init__(self):
        self._concepts = {
            "C0027051": {
                "id": "1",
                "cui": "C0027051",
                "preferredName": "Myocardial Infarction",
                "definitions": ["Heart attack caused by blocked blood flow"],
                "semanticTypes": ["T047"],
                "semanticGroup": "DISO",
                "vocabularies": ["SNOMED", "ICD10"],
                "synonyms": ["Heart Attack", "MI"],
            },
            "C0020538": {
                "id": "2",
                "cui": "C0020538",
                "preferredName": "Hypertension",
                "definitions": ["Elevated blood pressure"],
                "semanticTypes": ["T047"],
                "semanticGroup": "DISO",
                "vocabularies": ["SNOMED", "ICD10"],
                "synonyms": ["High Blood Pressure", "HTN"],
            },
            "C0003962": {
                "id": "3",
                "cui": "C0003962",
                "preferredName": "Aspirin",
                "definitions": ["Anti-inflammatory and antiplatelet medication"],
                "semanticTypes": ["T109", "T121"],
                "semanticGroup": "CHEM",
                "vocabularies": ["RxNorm", "SNOMED"],
                "synonyms": ["Acetylsalicylic acid", "ASA"],
            },
        }
        self._relationships = [
            {
                "id": "r1",
                "type": "MAY_CAUSE",
                "source_cui": "C0020538",
                "target_cui": "C0027051",
                "weight": 0.8,
                "confidence": 0.85,
            },
            {
                "id": "r2",
                "type": "TREATS",
                "source_cui": "C0003962",
                "target_cui": "C0027051",
                "weight": 0.9,
                "confidence": 0.95,
            },
        ]
        self._patients = {
            "P001": {
                "id": "P001",
                "mrn": "MRN12345",
            }
        }

    def get_concept(self, cui: str) -> dict[str, Any | None]:
        """Get a concept by CUI."""
        return self._concepts.get(cui)

    def get_concepts(self, cuis: list[str]) -> list[dict[str, Any]]:
        """Get multiple concepts by CUI."""
        return [self._concepts[cui] for cui in cuis if cui in self._concepts]

    def search_concepts(
        self,
        query: str,
        semantic_groups: list[str | None] = None,
        limit: int = 20,
        offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """Search for concepts."""
        results = []
        query_lower = query.lower()
        for concept in self._concepts.values():
            name_match = query_lower in concept["preferredName"].lower()
            synonym_match = any(query_lower in s.lower() for s in concept.get("synonyms", []))
            if name_match or synonym_match:
                if semantic_groups is None or concept.get("semanticGroup") in semantic_groups:
                    results.append(concept)
        total = len(results)
        return results[offset:offset + limit], total

    def get_relationships(self, cui: str, types: list[str | None] = None) -> list[dict[str, Any]]:
        """Get relationships for a concept."""
        results = []
        for rel in self._relationships:
            if rel["source_cui"] == cui or rel["target_cui"] == cui:
                if types is None or rel["type"] in types:
                    rel_copy = dict(rel)
                    rel_copy["source"] = self._concepts.get(rel["source_cui"])
                    rel_copy["target"] = self._concepts.get(rel["target_cui"])
                    results.append(rel_copy)
        return results

    def find_paths(
        self,
        source_cui: str,
        target_cui: str,
        max_hops: int = 3,
        relationship_types: list[str | None] = None
    ) -> list[dict[str, Any]]:
        """Find paths between concepts."""
        # Simple mock implementation
        if source_cui not in self._concepts or target_cui not in self._concepts:
            return []

        paths = []
        # Check for direct relationship
        for rel in self._relationships:
            if rel["source_cui"] == source_cui and rel["target_cui"] == target_cui:
                paths.append({
                    "id": f"path_{source_cui}_{target_cui}",
                    "source": self._concepts[source_cui],
                    "target": self._concepts[target_cui],
                    "steps": [
                        {"order": 0, "concept": self._concepts[source_cui], "score": 1.0},
                        {"order": 1, "concept": self._concepts[target_cui], "relationship": rel, "score": rel.get("confidence", 0.5)},
                    ],
                    "totalScore": rel.get("confidence", 0.5),
                    "hopCount": 1,
                    "explanation": f"Direct path via {rel['type']}",
                })
        return paths

    def get_patient(self, patient_id: str) -> dict[str, Any | None]:
        """Get a patient by ID."""
        return self._patients.get(patient_id)


class KGGraphQLService:
    """Service for executing GraphQL queries against the Knowledge Graph."""

    def __init__(self, data_source: MockKGDataSource | None = None):
        self.schema = create_kg_graphql_schema()
        self.executor = GraphQLExecutor(self.schema)
        self.data_source = data_source or MockKGDataSource()
        self._register_resolvers()

    def _register_resolvers(self):
        """Register all field resolvers."""
        # Query resolvers
        self.executor.register_resolver("Query", "concept", self._resolve_concept)
        self.executor.register_resolver("Query", "concepts", self._resolve_concepts)
        self.executor.register_resolver("Query", "searchConcepts", self._resolve_search_concepts)
        self.executor.register_resolver("Query", "findPaths", self._resolve_find_paths)
        self.executor.register_resolver("Query", "patient", self._resolve_patient)

        # Concept field resolvers
        self.executor.register_resolver("Concept", "relationships", self._resolve_concept_relationships)

    def _resolve_concept(self, parent, args, context):
        """Resolve a single concept."""
        cui = args.get("cui")
        return self.data_source.get_concept(cui)

    def _resolve_concepts(self, parent, args, context):
        """Resolve multiple concepts."""
        cuis = args.get("cuis", [])
        return self.data_source.get_concepts(cuis)

    def _resolve_search_concepts(self, parent, args, context):
        """Resolve concept search."""
        input_data = args.get("input", {})
        query = input_data.get("query", "")
        semantic_groups = input_data.get("semanticGroups")
        limit = input_data.get("limit", 20)
        offset = input_data.get("offset", 0)

        concepts, total = self.data_source.search_concepts(
            query=query,
            semantic_groups=semantic_groups,
            limit=limit,
            offset=offset
        )

        return {
            "concepts": concepts,
            "totalCount": total,
            "hasMore": offset + len(concepts) < total,
        }

    def _resolve_find_paths(self, parent, args, context):
        """Resolve path finding."""
        input_data = args.get("input", {})
        source_cui = input_data.get("sourceCui")
        target_cui = input_data.get("targetCui")
        max_hops = input_data.get("maxHops", 3)
        relationship_types = input_data.get("relationshipTypes")
        strategy = input_data.get("strategy", "BREADTH_FIRST")

        paths = self.data_source.find_paths(
            source_cui=source_cui,
            target_cui=target_cui,
            max_hops=max_hops,
            relationship_types=relationship_types
        )

        return {
            "paths": paths,
            "totalPaths": len(paths),
            "searchTime": 0.05,  # Mock timing
            "strategy": strategy,
        }

    def _resolve_patient(self, parent, args, context):
        """Resolve a patient."""
        patient_id = args.get("id")
        return self.data_source.get_patient(patient_id)

    def _resolve_concept_relationships(self, parent, args, context):
        """Resolve relationships for a concept."""
        cui = parent.get("cui")
        types = args.get("types")
        limit = args.get("limit", 50)

        relationships = self.data_source.get_relationships(cui, types)
        return relationships[:limit]

    def execute(
        self,
        query: str,
        variables: dict[str, Any | None] = None,
        operation_name: str | None = None,
        context: dict[str, Any | None] = None
    ) -> GraphQLResult:
        """Execute a GraphQL query."""
        return self.executor.execute(
            query=query,
            variables=variables,
            operation_name=operation_name,
            context=context
        )

    def get_schema_sdl(self) -> str:
        """Get the schema as SDL."""
        return self.schema.to_sdl()

    def introspect(self) -> dict[str, Any]:
        """Return introspection data for the schema."""
        types = []
        for type_def in self.schema.types.values():
            type_data = {
                "name": type_def.name,
                "kind": type_def.kind.value,
                "description": type_def.description,
            }
            if type_def.kind == GraphQLTypeKind.OBJECT:
                type_data["fields"] = [
                    {
                        "name": f.name,
                        "type": f.type_name,
                        "description": f.description,
                        "isList": f.is_list,
                        "isNonNull": f.is_non_null,
                    }
                    for f in type_def.fields.values()
                ]
            elif type_def.kind == GraphQLTypeKind.ENUM:
                type_data["enumValues"] = type_def.enum_values
            types.append(type_data)

        return {
            "__schema": {
                "queryType": {"name": self.schema.query_type},
                "mutationType": {"name": self.schema.mutation_type} if self.schema.mutation_type else None,
                "types": types,
            }
        }


# =============================================================================
# Singleton instance
# =============================================================================


_kg_graphql_service: KGGraphQLService | None = None
_kg_graphql_lock = threading.Lock()


def get_kg_graphql_service() -> KGGraphQLService:
    """Get the singleton KG GraphQL service instance."""
    global _kg_graphql_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _kg_graphql_service is None:
        with _kg_graphql_lock:
            if _kg_graphql_service is None:
                _kg_graphql_service = KGGraphQLService()
    return _kg_graphql_service


def reset_kg_graphql_service():
    """Reset the singleton instance (for testing)."""
    global _kg_graphql_service
    with _kg_graphql_lock:
        _kg_graphql_service = None
