-- Record native module searcher origins without changing the generated library.
local module, root, trace, abi = table.unpack(arg)
assert(_VERSION == 'Lua ' .. abi, 'selected native Lua ABI differs')
assert(package.loaded[module] == nil, 'generated Lua module shadows a native module')
assert(not package.searchpath(module, package.path) and not package.searchpath(module, package.cpath),
       'generated Lua module shadows a selected runtime dependency')
local log = assert(io.open(trace, 'w'))
for index, searcher in ipairs(package.searchers) do
  package.searchers[index] = function(name)
    local loader, origin = searcher(name)
    if type(loader) == 'function' and type(origin) == 'string' and origin:sub(1,1) == '/' then
      log:write(name, '\t', origin, '\n')
      log:flush()
    end
    return loader, origin
  end
end
package.path = root .. '/?.lua;' .. package.path
local exports = require(module)
assert(type(exports) == 'table' and next(exports) ~= nil,
       'native Haxe Lua library requires exposed exports')
log:close()
print('native Lua exports loaded')
