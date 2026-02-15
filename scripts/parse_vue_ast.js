#!/usr/bin/env node
/**
 * Vue SFC AST Parser
 *
 * Parses a .vue file and extracts TypeScript AST information using
 * @vue/compiler-sfc official parser with Babel AST
 *
 * Returns AST structure information about:
 * - TypeScript interface declarations
 * - Type annotations (generics, type parameters)
 * - Import statements (including type-only imports)
 * - Script lang attribute
 *
 * Usage: node parse_vue_ast.js <vue-file-path>
 * Output: JSON with AST structure information
 */

const { parse, compileScript } = require('@vue/compiler-sfc');
const fs = require('fs');

// Check command line arguments
if (process.argv.length < 3) {
  console.error(JSON.stringify({
    error: 'Usage: node parse_vue_ast.js <vue-file-path>'
  }));
  process.exit(1);
}

const filePath = process.argv[2];

// Read the Vue file
let source;
try {
  source = fs.readFileSync(filePath, 'utf-8');
} catch (err) {
  console.error(JSON.stringify({
    error: `Failed to read file: ${err.message}`
  }));
  process.exit(1);
}

// Parse the Vue SFC
let descriptor, parseErrors;
try {
  const result = parse(source, { filename: filePath });
  descriptor = result.descriptor;
  parseErrors = result.errors;
} catch (err) {
  console.error(JSON.stringify({
    error: `Parse error: ${err.message}`
  }));
  process.exit(1);
}

if (parseErrors.length > 0) {
  console.error(JSON.stringify({
    error: `Parse error: ${parseErrors[0].message}`
  }));
  process.exit(1);
}

// Extract script block (prefer scriptSetup over script)
const scriptBlock = descriptor.scriptSetup || descriptor.script;

if (!scriptBlock) {
  // No script block found - return empty result
  console.log(JSON.stringify({
    has_script_lang_ts: false,
    has_interfaces: false,
    has_type_annotations: false,
    has_imports: false,
    interfaces: [],
    type_annotations: [],
    imports: []
  }));
  process.exit(0);
}

const hasScriptLangTs = scriptBlock.lang === 'ts';

// Compile the script to get Babel AST
// scriptSetupAst will be an array of Babel Statement nodes
let compiled;
try {
  compiled = compileScript(descriptor, {
    id: filePath,
    babelParserPlugins: ['typescript']
  });
} catch (err) {
  console.error(JSON.stringify({
    error: `Compile error: ${err.message}`
  }));
  process.exit(1);
}

// Analyze AST (Babel Statement[] from @vue/compiler-sfc)
const interfaces = [];
const typeAnnotations = new Set();
const imports = [];

// scriptSetupAst is Statement[] from @babel/types
if (compiled.scriptSetupAst && Array.isArray(compiled.scriptSetupAst)) {
  compiled.scriptSetupAst.forEach(node => {
    // TSInterfaceDeclaration: interface Name { ... }
    if (node.type === 'TSInterfaceDeclaration') {
      interfaces.push(node.id.name);
    }

    // VariableDeclaration: const x = defineProps<T>()
    if (node.type === 'VariableDeclaration') {
      node.declarations.forEach(decl => {
        // Check for type parameters in function calls (e.g., defineProps<ComponentProps>())
        if (decl.init && decl.init.typeParameters) {
          decl.init.typeParameters.params.forEach(typeParam => {
            extractTypeNames(typeParam, typeAnnotations);
          });
        }

        // Check for type annotations on variables (e.g., const x: Type)
        if (decl.id.typeAnnotation) {
          extractTypeNames(decl.id.typeAnnotation, typeAnnotations);
        }
      });
    }

    // ImportDeclaration: import { x } from 'y' or import type { x } from 'y'
    if (node.type === 'ImportDeclaration') {
      imports.push({
        source: node.source.value,
        isTypeOnly: node.importKind === 'type'
      });
    }

    // TSTypeAliasDeclaration: type Name = ...
    if (node.type === 'TSTypeAliasDeclaration') {
      typeAnnotations.add(node.id.name);
    }

    // FunctionDeclaration with type parameters or return type
    if (node.type === 'FunctionDeclaration') {
      if (node.typeParameters) {
        node.typeParameters.params.forEach(typeParam => {
          if (typeParam.name) {
            typeAnnotations.add(typeParam.name);
          }
        });
      }
      if (node.returnType) {
        extractTypeNames(node.returnType, typeAnnotations);
      }
    }
  });
}

/**
 * Recursively extract type names from Babel TypeScript AST nodes
 * Handles TSTypeAnnotation, TSTypeReference, TSArrayType, etc.
 */
function extractTypeNames(typeNode, typeSet) {
  if (!typeNode) return;

  // TSTypeAnnotation wraps the actual type
  if (typeNode.type === 'TSTypeAnnotation' && typeNode.typeAnnotation) {
    extractTypeNames(typeNode.typeAnnotation, typeSet);
  }

  // TSTypeReference: a named type (e.g., ComponentProps, string)
  else if (typeNode.type === 'TSTypeReference' && typeNode.typeName) {
    // Handle simple identifier (e.g., ComponentProps)
    if (typeNode.typeName.type === 'Identifier') {
      typeSet.add(typeNode.typeName.name);
    }
    // Handle qualified name (e.g., Vue.Component)
    else if (typeNode.typeName.type === 'TSQualifiedName') {
      // Just add the full qualified name as string for now
      typeSet.add(extractQualifiedName(typeNode.typeName));
    }
  }

  // TSArrayType: Type[]
  else if (typeNode.type === 'TSArrayType') {
    extractTypeNames(typeNode.elementType, typeSet);
  }

  // TSUnionType: Type1 | Type2
  else if (typeNode.type === 'TSUnionType') {
    typeNode.types.forEach(t => extractTypeNames(t, typeSet));
  }

  // TSIntersectionType: Type1 & Type2
  else if (typeNode.type === 'TSIntersectionType') {
    typeNode.types.forEach(t => extractTypeNames(t, typeSet));
  }

  // TSTupleType: [Type1, Type2]
  else if (typeNode.type === 'TSTupleType') {
    typeNode.elementTypes.forEach(t => extractTypeNames(t, typeSet));
  }

  // TSTypeLiteral: { prop: Type }
  else if (typeNode.type === 'TSTypeLiteral') {
    typeNode.members.forEach(member => {
      if (member.typeAnnotation) {
        extractTypeNames(member.typeAnnotation, typeSet);
      }
    });
  }
}

/**
 * Extract qualified name as string (e.g., A.B.C -> "A.B.C")
 */
function extractQualifiedName(node) {
  if (node.type === 'Identifier') {
    return node.name;
  }
  if (node.type === 'TSQualifiedName') {
    return extractQualifiedName(node.left) + '.' + node.right.name;
  }
  return '';
}

// Build output
const output = {
  has_script_lang_ts: hasScriptLangTs,
  has_interfaces: interfaces.length > 0,
  has_type_annotations: typeAnnotations.size > 0,
  has_imports: imports.length > 0,
  interfaces: interfaces,
  type_annotations: Array.from(typeAnnotations),
  imports: imports
};

console.log(JSON.stringify(output));
process.exit(0);
